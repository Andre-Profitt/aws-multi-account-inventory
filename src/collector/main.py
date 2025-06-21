#!/usr/bin/env python3
"""AWS Multi-Account Inventory Collector"""

import json
import boto3
import click
import logging
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSInventoryCollector:
    def __init__(self, table_name: str = 'aws-company-inventory'):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.accounts = {}
        
    def load_config(self, config_file: str):
        """Load account configuration"""
        with open(config_file, 'r') as f:
            config = json.load(f)
            self.accounts = config.get('accounts', {})
            
    def assume_role(self, account_id: str, role_name: str) -> boto3.Session:
        """Assume role in target account"""
        sts = boto3.client('sts')
        role_arn = f'arn:aws:iam::{account_id}:role/{role_name}'
        
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='InventoryCollection'
        )
        
        creds = response['Credentials']
        return boto3.Session(
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )
        
    def collect_ec2_instances(self, session: boto3.Session, department: str, account_id: str) -> List[Dict]:
        """Collect EC2 instance inventory"""
        inventory = []
        ec2 = session.client('ec2')
        
        # Get all regions
        regions = [r['RegionName'] for r in ec2.describe_regions()['Regions']]
        
        for region in regions:
            regional_ec2 = session.client('ec2', region_name=region)
            
            try:
                response = regional_ec2.describe_instances()
                
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        inventory.append({
                            'pk': f"ec2#{account_id}#{region}#{instance['InstanceId']}",
                            'sk': datetime.utcnow().isoformat(),
                            'resource_type': 'ec2_instance',
                            'resource_id': instance['InstanceId'],
                            'department': department,
                            'account_id': account_id,
                            'region': region,
                            'instance_type': instance.get('InstanceType'),
                            'state': instance['State']['Name'],
                            'launch_time': instance.get('LaunchTime', '').isoformat() if instance.get('LaunchTime') else ''
                        })
            except Exception as e:
                logger.error(f"Error in {region}: {str(e)}")
                
        return inventory
        
    def collect_inventory(self):
        """Collect inventory from all accounts"""
        all_inventory = []
        
        for dept, account_info in self.accounts.items():
            logger.info(f"Collecting from {dept} ({account_info['account_id']})")
            
            try:
                session = self.assume_role(account_info['account_id'], account_info['role_name'])
                inventory = self.collect_ec2_instances(session, dept, account_info['account_id'])
                all_inventory.extend(inventory)
                logger.info(f"Collected {len(inventory)} resources from {dept}")
            except Exception as e:
                logger.error(f"Failed to collect from {dept}: {str(e)}")
                
        # Store in DynamoDB
        with self.table.batch_writer() as batch:
            for item in all_inventory:
                batch.put_item(Item=item)
                
        logger.info(f"Total resources collected: {len(all_inventory)}")
        return all_inventory

@click.command()
@click.option('--config', default='config/accounts.json', help='Config file path')
@click.option('--dry-run', is_flag=True, help='Show what would be collected')
def main(config, dry_run):
    """AWS Multi-Account Inventory Collector"""
    collector = AWSInventoryCollector()
    collector.load_config(config)
    
    if dry_run:
        logger.info("DRY RUN - Would collect from:")
        for dept, info in collector.accounts.items():
            logger.info(f"  {dept}: {info['account_id']}")
    else:
        collector.collect_inventory()

if __name__ == '__main__':
    main()