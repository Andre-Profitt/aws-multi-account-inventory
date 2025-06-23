import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.main import AWSInventoryCollector

def lambda_handler(event, context):
    """Lambda handler for scheduled collection"""
    
    # Check if config is provided in event, environment, or file
    config_data = None
    
    # Option 1: Config passed in event
    if 'accounts' in event:
        config_data = event
    
    # Option 2: Config in environment variable
    elif os.environ.get('ACCOUNTS_CONFIG'):
        config_data = json.loads(os.environ['ACCOUNTS_CONFIG'])
    
    # Option 3: Config file in Lambda package
    else:
        config_paths = [
            '/opt/config/accounts.json',  # Lambda layer
            'config/accounts.json',        # Package root
            '/tmp/accounts.json'           # Temp directory
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                break
    
    if not config_data or not config_data.get('accounts'):
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'No account configuration found',
                'help': 'Provide config via event payload, ACCOUNTS_CONFIG env var, or config file'
            })
        }
    
    # Initialize collector
    collector = AWSInventoryCollector(
        table_name=os.environ.get('DYNAMODB_TABLE_NAME', 'aws-inventory')
    )
    
    # Load config directly instead of from file
    collector.accounts = config_data.get('accounts', {})
    
    try:
        inventory = collector.collect_inventory()
        
        # Summary by resource type
        summary = {}
        for item in inventory:
            rt = item.get('resource_type', 'unknown')
            summary[rt] = summary.get(rt, 0) + 1
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully collected {len(inventory)} resources',
                'summary': summary,
                'accounts_processed': list(collector.accounts.keys())
            })
        }
    except Exception as e:
        print(f"Error during collection: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }