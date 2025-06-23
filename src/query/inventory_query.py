#!/usr/bin/env python3
"""Query AWS Inventory Data from DynamoDB"""

import boto3
import click
import json
from tabulate import tabulate
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from botocore.exceptions import ClientError

class InventoryQuery:
    def __init__(self, table_name: str = 'aws-inventory'):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.client = boto3.client('dynamodb')
        
    def get_summary(self) -> Dict[str, int]:
        """Get inventory summary by resource type and account"""
        try:
            # Use scan to get all items (for small datasets)
            # For larger datasets, consider using GSI queries
            response = self.table.scan()
            
            summary = {
                'by_type': {},
                'by_account': {},
                'total': 0
            }
            
            for item in response['Items']:
                resource_type = item.get('resource_type', 'unknown')
                account_name = item.get('account_name', 'unknown')
                
                # Count by type
                summary['by_type'][resource_type] = summary['by_type'].get(resource_type, 0) + 1
                
                # Count by account
                summary['by_account'][account_name] = summary['by_account'].get(account_name, 0) + 1
                
                summary['total'] += 1
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                for item in response['Items']:
                    resource_type = item.get('resource_type', 'unknown')
                    account_name = item.get('account_name', 'unknown')
                    summary['by_type'][resource_type] = summary['by_type'].get(resource_type, 0) + 1
                    summary['by_account'][account_name] = summary['by_account'].get(account_name, 0) + 1
                    summary['total'] += 1
                    
            return summary
        except ClientError as e:
            print(f"Error querying DynamoDB: {e}")
            return {'by_type': {}, 'by_account': {}, 'total': 0}
    
    def get_resources_by_account(self, account_id: str) -> List[Dict]:
        """Get all resources for a specific account"""
        try:
            response = self.table.query(
                IndexName='account-resource-index',
                KeyConditionExpression='account_id = :account_id',
                ExpressionAttributeValues={
                    ':account_id': account_id
                }
            )
            return response['Items']
        except ClientError as e:
            print(f"Error querying resources for account {account_id}: {e}")
            return []
    
    def get_recent_resources(self, hours: int = 24) -> List[Dict]:
        """Get resources discovered in the last N hours"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff_time.isoformat()
        
        try:
            # This requires a scan with filter - not efficient for large datasets
            response = self.table.scan(
                FilterExpression='#ts > :cutoff',
                ExpressionAttributeNames={
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':cutoff': cutoff_iso
                }
            )
            return response['Items']
        except ClientError as e:
            print(f"Error querying recent resources: {e}")
            return []
    
    def export_to_json(self, filename: str = 'inventory_export.json'):
        """Export all inventory data to JSON file"""
        try:
            all_items = []
            response = self.table.scan()
            all_items.extend(response['Items'])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                all_items.extend(response['Items'])
            
            # Convert to JSON-serializable format
            for item in all_items:
                # Convert datetime objects to strings
                if 'timestamp' in item:
                    item['timestamp'] = str(item['timestamp'])
                if 'launch_time' in item:
                    item['launch_time'] = str(item['launch_time'])
                if 'create_time' in item:
                    item['create_time'] = str(item['create_time'])
                if 'creation_date' in item:
                    item['creation_date'] = str(item['creation_date'])
            
            with open(filename, 'w') as f:
                json.dump(all_items, f, indent=2, default=str)
            
            print(f"Exported {len(all_items)} items to {filename}")
            return len(all_items)
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return 0
    
    def get_resource_details(self, resource_id: str) -> List[Dict]:
        """Get details for a specific resource ID"""
        try:
            # Scan with filter (not efficient, but works for any resource ID)
            response = self.table.scan(
                FilterExpression='resource_id = :rid',
                ExpressionAttributeValues={
                    ':rid': resource_id
                }
            )
            return response['Items']
        except ClientError as e:
            print(f"Error querying resource {resource_id}: {e}")
            return []

@click.command()
@click.option('--action', type=click.Choice(['summary', 'by-account', 'recent', 'export', 'details']), 
              default='summary', help='Query action to perform')
@click.option('--account-id', help='Account ID for account-specific queries')
@click.option('--hours', default=24, help='Hours to look back for recent resources')
@click.option('--resource-id', help='Resource ID for detailed lookup')
@click.option('--output', default='inventory_export.json', help='Output filename for export')
@click.option('--table', default='aws-inventory', help='DynamoDB table name')
def main(action, account_id, hours, resource_id, output, table):
    """Query AWS Inventory Data"""
    query = InventoryQuery(table_name=table)
    
    if action == 'summary':
        summary = query.get_summary()
        
        print("\n🌍 AWS Inventory Summary")
        print("=" * 50)
        print(f"Total Resources: {summary['total']}")
        
        print("\n📊 Resources by Type:")
        if summary['by_type']:
            type_data = [[rtype, count] for rtype, count in sorted(summary['by_type'].items())]
            print(tabulate(type_data, headers=['Resource Type', 'Count'], tablefmt='grid'))
        
        print("\n🏢 Resources by Account:")
        if summary['by_account']:
            account_data = [[account, count] for account, count in sorted(summary['by_account'].items())]
            print(tabulate(account_data, headers=['Account', 'Count'], tablefmt='grid'))
    
    elif action == 'by-account':
        if not account_id:
            print("Error: --account-id required for by-account action")
            return
        
        resources = query.get_resources_by_account(account_id)
        print(f"\n📦 Resources in Account {account_id}")
        print("=" * 50)
        
        if resources:
            # Group by type
            by_type = {}
            for r in resources:
                rtype = r.get('resource_type', 'unknown')
                by_type.setdefault(rtype, []).append(r)
            
            for rtype, items in sorted(by_type.items()):
                print(f"\n{rtype} ({len(items)} items):")
                for item in items[:5]:  # Show first 5
                    print(f"  - {item.get('resource_id', 'N/A')} ({item.get('resource_name', 'unnamed')})")
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")
        else:
            print("No resources found for this account")
    
    elif action == 'recent':
        resources = query.get_recent_resources(hours)
        print(f"\n🕐 Resources discovered in the last {hours} hours")
        print("=" * 50)
        
        if resources:
            recent_data = []
            for r in resources[:20]:  # Show most recent 20
                recent_data.append([
                    r.get('timestamp', 'N/A')[:19],  # Trim microseconds
                    r.get('account_name', 'N/A'),
                    r.get('resource_type', 'N/A'),
                    r.get('resource_id', 'N/A')
                ])
            print(tabulate(recent_data, 
                         headers=['Timestamp', 'Account', 'Type', 'Resource ID'], 
                         tablefmt='grid'))
            if len(resources) > 20:
                print(f"\n... and {len(resources) - 20} more resources")
        else:
            print("No recent resources found")
    
    elif action == 'export':
        count = query.export_to_json(output)
        if count > 0:
            print(f"\n✅ Successfully exported {count} resources to {output}")
    
    elif action == 'details':
        if not resource_id:
            print("Error: --resource-id required for details action")
            return
        
        resources = query.get_resource_details(resource_id)
        if resources:
            print(f"\n🔍 Details for Resource: {resource_id}")
            print("=" * 50)
            for r in resources:
                print(json.dumps(r, indent=2, default=str))
        else:
            print(f"No resource found with ID: {resource_id}")


if __name__ == '__main__':
    main()