import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.main import AWSInventoryCollector

def lambda_handler(event, context):
    """Lambda handler for scheduled collection"""
    collector = AWSInventoryCollector()
    collector.load_config('/opt/config/accounts.json')
    
    try:
        inventory = collector.collect_inventory()
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Collected {len(inventory)} resources'
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }