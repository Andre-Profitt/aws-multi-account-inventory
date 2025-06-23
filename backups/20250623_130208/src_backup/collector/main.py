#!/usr/bin/env python3
<<<<<<< HEAD
"""
AWS Multi-Account Inventory Collector

This module collects inventory from multiple AWS accounts and stores it in DynamoDB.
"""

import boto3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
import concurrent.futures
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AWSInventoryCollector:
    """Collects AWS resource inventory across multiple accounts"""
    
    def __init__(self, table_name: str = 'aws-inventory'):
        """Initialize the collector
        
        Args:
            table_name: Name of the DynamoDB table for storing inventory
        """
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.sts = boto3.client('sts')
        self.accounts = {}
        
    def load_config(self, config_file: str):
        """Load account configuration from file
        
        Args:
            config_file: Path to JSON configuration file
        """
=======
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
>>>>>>> origin/main
        with open(config_file, 'r') as f:
            config = json.load(f)
            self.accounts = config.get('accounts', {})
            
    def assume_role(self, account_id: str, role_name: str) -> boto3.Session:
<<<<<<< HEAD
        """Assume role in target account
        
        Args:
            account_id: AWS Account ID
            role_name: Name of the role to assume
            
        Returns:
            Boto3 session for the assumed role
        """
        try:
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
            
            response = self.sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f'inventory-collector-{account_id}',
                ExternalId='inventory-collector'
            )
            
            credentials = response['Credentials']
            
            session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
            
            logger.info(f"Successfully assumed role in account {account_id}")
            return session
            
        except ClientError as e:
            logger.error(f"Failed to assume role in account {account_id}: {e}")
            raise
            
    def get_regions(self, session: boto3.Session) -> List[str]:
        """Get list of enabled regions
        
        Args:
            session: Boto3 session
            
        Returns:
            List of region names
        """
        ec2 = session.client('ec2', region_name='us-east-1')
        response = ec2.describe_regions(AllRegions=False)
        return [r['RegionName'] for r in response['Regions']]
        
    def collect_ec2_instances(self, session: boto3.Session, region: str, account_id: str, account_name: str) -> List[Dict]:
        """Collect EC2 instances from a region
        
        Args:
            session: Boto3 session
            region: AWS region
            account_id: AWS Account ID
            account_name: Account name/alias
            
        Returns:
            List of EC2 instance inventory items
        """
        items = []
        try:
            ec2 = session.client('ec2', region_name=region)
            
            paginator = ec2.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        item = {
                            'composite_key': f"{account_id}#ec2#{instance['InstanceId']}",
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'account_id': account_id,
                            'account_name': account_name,
                            'region': region,
                            'resource_type': 'ec2_instance',
                            'resource_id': instance['InstanceId'],
                            'resource_name': self._get_tag_value(instance.get('Tags', []), 'Name'),
                            'instance_type': instance.get('InstanceType'),
                            'state': instance['State']['Name'],
                            'launch_time': instance.get('LaunchTime', '').isoformat() if instance.get('LaunchTime') else None,
                            'availability_zone': instance.get('Placement', {}).get('AvailabilityZone'),
                            'vpc_id': instance.get('VpcId'),
                            'subnet_id': instance.get('SubnetId'),
                            'public_ip': instance.get('PublicIpAddress'),
                            'private_ip': instance.get('PrivateIpAddress'),
                            'tags': instance.get('Tags', [])
                        }
                        items.append(item)
                        
            logger.info(f"Collected {len(items)} EC2 instances from {account_name}/{region}")
            
        except ClientError as e:
            logger.error(f"Error collecting EC2 instances from {account_name}/{region}: {e}")
            
        return items
        
    def collect_rds_instances(self, session: boto3.Session, region: str, account_id: str, account_name: str) -> List[Dict]:
        """Collect RDS instances from a region
        
        Args:
            session: Boto3 session
            region: AWS region
            account_id: AWS Account ID
            account_name: Account name/alias
            
        Returns:
            List of RDS instance inventory items
        """
        items = []
        try:
            rds = session.client('rds', region_name=region)
            
            paginator = rds.get_paginator('describe_db_instances')
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    item = {
                        'composite_key': f"{account_id}#rds#{db['DBInstanceIdentifier']}",
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'account_id': account_id,
                        'account_name': account_name,
                        'region': region,
                        'resource_type': 'rds_instance',
                        'resource_id': db['DBInstanceIdentifier'],
                        'resource_name': db['DBInstanceIdentifier'],
                        'instance_class': db.get('DBInstanceClass'),
                        'engine': db.get('Engine'),
                        'engine_version': db.get('EngineVersion'),
                        'status': db.get('DBInstanceStatus'),
                        'multi_az': db.get('MultiAZ', False),
                        'storage_type': db.get('StorageType'),
                        'allocated_storage': db.get('AllocatedStorage'),
                        'vpc_id': db.get('DBSubnetGroup', {}).get('VpcId') if db.get('DBSubnetGroup') else None,
                        'create_time': db.get('InstanceCreateTime', '').isoformat() if db.get('InstanceCreateTime') else None,
                        'tags': db.get('TagList', [])
                    }
                    items.append(item)
                    
            logger.info(f"Collected {len(items)} RDS instances from {account_name}/{region}")
            
        except ClientError as e:
            logger.error(f"Error collecting RDS instances from {account_name}/{region}: {e}")
            
        return items
        
    def collect_s3_buckets(self, session: boto3.Session, account_id: str, account_name: str) -> List[Dict]:
        """Collect S3 buckets (global service)
        
        Args:
            session: Boto3 session
            account_id: AWS Account ID
            account_name: Account name/alias
            
        Returns:
            List of S3 bucket inventory items
        """
        items = []
        try:
            s3 = session.client('s3')
            
            response = s3.list_buckets()
            for bucket in response.get('Buckets', []):
                bucket_name = bucket['Name']
                
                # Get bucket location
                try:
                    location_response = s3.get_bucket_location(Bucket=bucket_name)
                    region = location_response.get('LocationConstraint', 'us-east-1')
                    if region is None:
                        region = 'us-east-1'
                except:
                    region = 'unknown'
                    
                # Get bucket tags
                tags = []
                try:
                    tag_response = s3.get_bucket_tagging(Bucket=bucket_name)
                    tags = tag_response.get('TagSet', [])
                except:
                    pass
                    
                item = {
                    'composite_key': f"{account_id}#s3#{bucket_name}",
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'account_id': account_id,
                    'account_name': account_name,
                    'region': region,
                    'resource_type': 's3_bucket',
                    'resource_id': bucket_name,
                    'resource_name': bucket_name,
                    'creation_date': bucket.get('CreationDate', '').isoformat() if bucket.get('CreationDate') else None,
                    'tags': tags
                }
                items.append(item)
                
            logger.info(f"Collected {len(items)} S3 buckets from {account_name}")
            
        except ClientError as e:
            logger.error(f"Error collecting S3 buckets from {account_name}: {e}")
            
        return items
        
    def _get_tag_value(self, tags: List[Dict], key: str) -> str:
        """Extract tag value by key
        
        Args:
            tags: List of tag dictionaries
            key: Tag key to search for
            
        Returns:
            Tag value or empty string
        """
        for tag in tags:
            if tag.get('Key') == key:
                return tag.get('Value', '')
        return ''
        
    def collect_account_inventory(self, account_name: str, account_info: Dict) -> List[Dict]:
        """Collect inventory from a single account
        
        Args:
            account_name: Account name/alias
            account_info: Account configuration
            
        Returns:
            List of inventory items
        """
        account_id = account_info['account_id']
        role_name = account_info.get('role_name', 'InventoryRole')
        
        try:
            # Assume role in target account
            session = self.assume_role(account_id, role_name)
            
            # Get enabled regions
            regions = self.get_regions(session)
            
            all_items = []
            
            # Collect S3 buckets (global)
            all_items.extend(self.collect_s3_buckets(session, account_id, account_name))
            
            # Collect regional resources
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                
                for region in regions:
                    # EC2 instances
                    futures.append(
                        executor.submit(self.collect_ec2_instances, session, region, account_id, account_name)
                    )
                    
                    # RDS instances
                    futures.append(
                        executor.submit(self.collect_rds_instances, session, region, account_id, account_name)
                    )
                    
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        items = future.result()
                        all_items.extend(items)
                    except Exception as e:
                        logger.error(f"Error in collection task: {e}")
                        
            return all_items
            
        except Exception as e:
            logger.error(f"Error collecting inventory from account {account_name}: {e}")
            return []
            
    def collect_inventory(self) -> List[Dict]:
        """Collect inventory from all configured accounts
        
        Returns:
            List of all inventory items
        """
        all_inventory = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.collect_account_inventory, name, info): name
                for name, info in self.accounts.items()
            }
            
            for future in concurrent.futures.as_completed(futures):
                account_name = futures[future]
                try:
                    items = future.result()
                    all_inventory.extend(items)
                    logger.info(f"Collected {len(items)} items from {account_name}")
                except Exception as e:
                    logger.error(f"Error collecting from {account_name}: {e}")
                    
        # Store in DynamoDB
        self.store_inventory(all_inventory)
        
        return all_inventory
        
    def store_inventory(self, items: List[Dict]):
        """Store inventory items in DynamoDB
        
        Args:
            items: List of inventory items
        """
        if not items:
            logger.info("No items to store")
            return
            
        # Batch write to DynamoDB
        with self.table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
                
        logger.info(f"Stored {len(items)} items in DynamoDB")


def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AWS Multi-Account Inventory Collector')
    parser.add_argument('--config', required=True, help='Path to accounts configuration file')
    parser.add_argument('--table', default='aws-inventory', help='DynamoDB table name')
    
    args = parser.parse_args()
    
    collector = AWSInventoryCollector(table_name=args.table)
    collector.load_config(args.config)
    
    inventory = collector.collect_inventory()
    
    print(f"\nCollection complete! Total items: {len(inventory)}")
    
    # Summary by resource type
    summary = {}
    for item in inventory:
        rt = item.get('resource_type', 'unknown')
        summary[rt] = summary.get(rt, 0) + 1
        
    print("\nResource Summary:")
    for resource_type, count in sorted(summary.items()):
        print(f"  {resource_type}: {count}")

=======
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
>>>>>>> origin/main

if __name__ == '__main__':
    main()