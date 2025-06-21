#!/usr/bin/env python3
"""Query AWS Inventory Data"""

import boto3
import click
import json
from tabulate import tabulate
from datetime import datetime, timedelta

class InventoryQuery:
    def __init__(self, table_name: str = 'aws-company-inventory'):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        
    def count_resources(self, resource_type: str = None):
        """Count resources by type"""
        if resource_type:
            response = self.table.query(
                IndexName='resource-type-index',
                KeyConditionExpression='resource_type = :rt',
                ExpressionAttributeValues={':rt': resource_type}
            )
            return len(response['Items'])
        return 0
        
    def get_summary(self):
        """Get inventory summary"""
        # This is simplified - real implementation would use GSI
        response = self.table.scan()
        
        summary = {}
        for item in response['Items']:
            rt = item.get('resource_type', 'unknown')
            summary[rt] = summary.get(rt, 0) + 1
            
        return summary

@click.command()
@click.option('--action', type=click.Choice(['summary', 'count', 'export']), default='summary')
@click.option('--resource-type', help='Resource type to filter')
def main(action, resource_type):
    """Query AWS Inventory"""
    query = InventoryQuery()
    
    if action == 'summary':
        summary = query.get_summary()
        print("\nAWS Inventory Summary")
        print("=" * 40)
        for rtype, count in summary.items():
            print(f"{rtype}: {count}")
    elif action == 'count':
        count = query.count_resources(resource_type)
        print(f"\n{resource_type}: {count} resources")

if __name__ == '__main__':
    main()