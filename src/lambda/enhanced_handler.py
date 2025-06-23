import json
import os
import sys
import boto3
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import traceback

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collector.enhanced_main import AWSInventoryCollector
from query.enhanced_inventory_query import InventoryQuery

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_sns_notification(subject: str, message: str, topic_arn: str = None):
    """Send SNS notification for alerts"""
    if not topic_arn:
        topic_arn = os.environ.get('SNS_TOPIC_ARN')
    
    if not topic_arn:
        logger.warning("No SNS topic ARN configured")
        return
    
    try:
        sns = boto3.client('sns')
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        logger.info(f"SNS notification sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {e}")


def put_cloudwatch_metrics(metrics: List[Dict[str, Any]]):
    """Send custom metrics to CloudWatch"""
    try:
        cloudwatch = boto3.client('cloudwatch')
        
        metric_data = []
        for metric in metrics:
            metric_data.append({
                'MetricName': metric['name'],
                'Value': metric['value'],
                'Unit': metric.get('unit', 'Count'),
                'Timestamp': datetime.now(timezone.utc),
                'Dimensions': [
                    {'Name': 'Function', 'Value': 'InventoryCollector'}
                ]
            })
        
        if metric_data:
            cloudwatch.put_metric_data(
                Namespace='AWSInventory',
                MetricData=metric_data
            )
            logger.info(f"Published {len(metric_data)} metrics to CloudWatch")
    except Exception as e:
        logger.error(f"Failed to put CloudWatch metrics: {e}")


def lambda_handler(event, context):
    """Enhanced Lambda handler with monitoring and cost analysis"""
    
    start_time = datetime.now(timezone.utc)
    
    # Determine the action
    action = event.get('action', 'collect')
    
    if action == 'collect':
        return handle_collection(event, context, start_time)
    elif action == 'analyze_cost':
        return handle_cost_analysis(event, context)
    elif action == 'check_security':
        return handle_security_check(event, context)
    elif action == 'cleanup_stale':
        return handle_stale_cleanup(event, context)
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Unknown action: {action}'})
        }


def handle_collection(event, context, start_time):
    """Handle inventory collection with enhanced monitoring"""
    
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
        error_msg = "No account configuration found"
        logger.error(error_msg)
        
        # Send alert
        send_sns_notification(
            "Inventory Collection Failed - Configuration Error",
            f"Error: {error_msg}\n\nPlease check Lambda configuration."
        )
        
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': error_msg,
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
        # Collect inventory
        inventory = collector.collect_inventory()
        
        # Calculate metrics
        end_time = datetime.now(timezone.utc)
        duration_seconds = (end_time - start_time).total_seconds()
        
        # Summary by resource type
        summary = {}
        total_cost = 0
        errors_by_account = {}
        
        for item in inventory:
            rt = item.get('resource_type', 'unknown')
            summary[rt] = summary.get(rt, 0) + 1
            total_cost += item.get('estimated_monthly_cost', 0)
            
            # Track any collection errors
            if 'error' in item:
                account = item.get('account_name', 'unknown')
                errors_by_account[account] = errors_by_account.get(account, 0) + 1
        
        # Send CloudWatch metrics
        metrics = [
            {'name': 'ResourcesCollected', 'value': len(inventory)},
            {'name': 'CollectionDuration', 'value': duration_seconds, 'unit': 'Seconds'},
            {'name': 'AccountsProcessed', 'value': len(collector.accounts)},
            {'name': 'EstimatedMonthlyCost', 'value': total_cost, 'unit': 'None'},
            {'name': 'CollectionErrors', 'value': len(errors_by_account)}
        ]
        
        put_cloudwatch_metrics(metrics)
        
        # Check for alerts
        if total_cost > float(os.environ.get('COST_ALERT_THRESHOLD', '10000')):
            send_sns_notification(
                "High AWS Cost Alert",
                f"Total monthly cost (${total_cost:,.2f}) exceeds threshold.\n\n"
                f"Resources collected: {len(inventory)}\n"
                f"Accounts: {list(collector.accounts.keys())}"
            )
        
        if errors_by_account:
            send_sns_notification(
                "Inventory Collection Errors",
                f"Errors occurred during collection:\n\n" +
                "\n".join([f"- {account}: {count} errors" 
                          for account, count in errors_by_account.items()])
            )
        
        # Log summary
        logger.info(f"Collection completed in {duration_seconds:.2f}s")
        logger.info(f"Collected {len(inventory)} resources")
        logger.info(f"Estimated monthly cost: ${total_cost:,.2f}")
        logger.info(f"Summary: {json.dumps(summary)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully collected {len(inventory)} resources',
                'duration_seconds': duration_seconds,
                'summary': summary,
                'total_monthly_cost': round(total_cost, 2),
                'accounts_processed': list(collector.accounts.keys()),
                'errors': errors_by_account if errors_by_account else None
            })
        }
        
    except Exception as e:
        error_msg = f"Error during collection: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Send alert
        send_sns_notification(
            "Inventory Collection Failed",
            f"Error: {error_msg}\n\nStack trace:\n{traceback.format_exc()}"
        )
        
        # Send error metric
        put_cloudwatch_metrics([
            {'name': 'CollectionErrors', 'value': 1}
        ])
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }


def handle_cost_analysis(event, context):
    """Handle cost analysis requests"""
    
    try:
        query = InventoryQuery(
            table_name=os.environ.get('DYNAMODB_TABLE_NAME', 'aws-inventory')
        )
        
        analysis = query.get_cost_analysis()
        
        # Check if we should send cost report
        if event.get('send_report', False):
            report = generate_cost_report(analysis)
            
            send_sns_notification(
                f"AWS Cost Analysis Report - {datetime.now().strftime('%Y-%m-%d')}",
                report
            )
            
            # Save to S3 if configured
            s3_bucket = os.environ.get('REPORTS_S3_BUCKET')
            if s3_bucket:
                s3 = boto3.client('s3')
                key = f"cost-reports/{datetime.now().strftime('%Y/%m/%d')}/cost-analysis.json"
                
                s3.put_object(
                    Bucket=s3_bucket,
                    Key=key,
                    Body=json.dumps(analysis, indent=2, default=str),
                    ContentType='application/json'
                )
                
                logger.info(f"Cost report saved to s3://{s3_bucket}/{key}")
        
        # Send cost metrics
        metrics = [
            {'name': 'TotalMonthlyCost', 'value': analysis['total_monthly_cost']},
            {'name': 'PotentialSavings', 'value': analysis['total_potential_savings']},
            {'name': 'IdleResources', 'value': len(analysis['idle_resources'])},
            {'name': 'OversizedResources', 'value': len(analysis['oversized_resources'])}
        ]
        
        put_cloudwatch_metrics(metrics)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'total_monthly_cost': analysis['total_monthly_cost'],
                'yearly_projection': analysis['yearly_projection'],
                'potential_savings': analysis['total_potential_savings'],
                'top_expensive_resources': analysis['top_expensive_resources'][:10],
                'optimization_opportunities': {
                    'idle_resources': len(analysis['idle_resources']),
                    'oversized_resources': len(analysis['oversized_resources'])
                }
            })
        }
        
    except Exception as e:
        logger.error(f"Error during cost analysis: {e}")
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }


def handle_security_check(event, context):
    """Handle security compliance checks"""
    
    try:
        query = InventoryQuery(
            table_name=os.environ.get('DYNAMODB_TABLE_NAME', 'aws-inventory')
        )
        
        analysis = query.get_cost_analysis()
        
        security_issues = {
            'unencrypted_resources': analysis['unencrypted_resources'],
            'public_resources': analysis['public_resources'],
            'total_issues': (len(analysis['unencrypted_resources']) + 
                           len(analysis['public_resources']))
        }
        
        # Send alert if issues found
        if security_issues['total_issues'] > 0:
            alert_message = f"Security issues found:\n\n"
            alert_message += f"- Unencrypted resources: {len(security_issues['unencrypted_resources'])}\n"
            alert_message += f"- Public resources: {len(security_issues['public_resources'])}\n\n"
            
            # Add details of first few issues
            for resource in security_issues['unencrypted_resources'][:5]:
                alert_message += f"\nUnencrypted {resource['type']}: {resource['resource_id']}\n"
                alert_message += f"  Issue: {resource['issue']}\n"
                alert_message += f"  Fix: {resource['recommendation']}\n"
            
            for resource in security_issues['public_resources'][:5]:
                alert_message += f"\nPublic {resource['type']}: {resource['resource_id']}\n"
                alert_message += f"  Issue: {resource['issue']}\n"
                alert_message += f"  Fix: {resource['recommendation']}\n"
            
            send_sns_notification(
                f"Security Alert - {security_issues['total_issues']} Issues Found",
                alert_message
            )
        
        # Send security metrics
        metrics = [
            {'name': 'UnencryptedResources', 'value': len(security_issues['unencrypted_resources'])},
            {'name': 'PublicResources', 'value': len(security_issues['public_resources'])},
            {'name': 'TotalSecurityIssues', 'value': security_issues['total_issues']}
        ]
        
        put_cloudwatch_metrics(metrics)
        
        return {
            'statusCode': 200,
            'body': json.dumps(security_issues)
        }
        
    except Exception as e:
        logger.error(f"Error during security check: {e}")
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }


def handle_stale_cleanup(event, context):
    """Identify stale resources for cleanup"""
    
    try:
        query = InventoryQuery(
            table_name=os.environ.get('DYNAMODB_TABLE_NAME', 'aws-inventory')
        )
        
        days = event.get('days', 90)
        stale_resources = query.get_stale_resources(days)
        
        total_savings = sum(r['monthly_cost'] for r in stale_resources)
        
        if stale_resources:
            # Generate cleanup report
            report = f"Stale Resource Report (>{days} days)\n\n"
            report += f"Found {len(stale_resources)} stale resources\n"
            report += f"Potential monthly savings: ${total_savings:,.2f}\n\n"
            
            # Group by type
            by_type = {}
            for resource in stale_resources:
                rtype = resource['resource_type']
                if rtype not in by_type:
                    by_type[rtype] = {'count': 0, 'cost': 0}
                by_type[rtype]['count'] += 1
                by_type[rtype]['cost'] += resource['monthly_cost']
            
            report += "Summary by type:\n"
            for rtype, info in by_type.items():
                report += f"- {rtype}: {info['count']} resources (${info['cost']:,.2f}/month)\n"
            
            # Save report to S3
            s3_bucket = os.environ.get('REPORTS_S3_BUCKET')
            if s3_bucket:
                s3 = boto3.client('s3')
                
                # Save detailed JSON
                key = f"cleanup-reports/{datetime.now().strftime('%Y/%m/%d')}/stale-resources.json"
                s3.put_object(
                    Bucket=s3_bucket,
                    Key=key,
                    Body=json.dumps(stale_resources, indent=2, default=str),
                    ContentType='application/json'
                )
                
                # Save summary report
                key = f"cleanup-reports/{datetime.now().strftime('%Y/%m/%d')}/summary.txt"
                s3.put_object(
                    Bucket=s3_bucket,
                    Key=key,
                    Body=report,
                    ContentType='text/plain'
                )
                
                logger.info(f"Cleanup report saved to S3")
            
            # Send notification if significant savings
            if total_savings > 100:
                send_sns_notification(
                    f"Cleanup Opportunity - Save ${total_savings:,.2f}/month",
                    report
                )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'stale_resources_count': len(stale_resources),
                'potential_monthly_savings': round(total_savings, 2),
                'summary_by_type': by_type if stale_resources else {}
            })
        }
        
    except Exception as e:
        logger.error(f"Error during stale cleanup check: {e}")
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'type': type(e).__name__
            })
        }


def generate_cost_report(analysis: Dict[str, Any]) -> str:
    """Generate formatted cost report"""
    
    report = f"""AWS Cost Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

EXECUTIVE SUMMARY
================
Total Monthly Cost: ${analysis['total_monthly_cost']:,.2f}
Yearly Projection: ${analysis['yearly_projection']:,.2f}
Potential Monthly Savings: ${analysis['total_potential_savings']:,.2f}
Potential Yearly Savings: ${analysis['yearly_potential_savings']:,.2f}

TOP 10 MOST EXPENSIVE RESOURCES
==============================
"""
    
    for i, resource in enumerate(analysis['top_expensive_resources'][:10], 1):
        report += f"\n{i}. {resource['resource_type']} - {resource['resource_id']}\n"
        report += f"   Account: {resource['account_name']}, Region: {resource['region']}\n"
        report += f"   Monthly Cost: ${resource['monthly_cost']:,.2f}\n"
    
    if analysis['idle_resources']:
        report += f"\n\nIDLE RESOURCES ({len(analysis['idle_resources'])} found)\n"
        report += "=" * 40 + "\n"
        total_idle_cost = sum(r.get('potential_savings', 0) for r in analysis['idle_resources'])
        report += f"Total potential savings: ${total_idle_cost:,.2f}/month\n\n"
        
        for resource in analysis['idle_resources'][:10]:
            report += f"• {resource['type']} - {resource['resource_id']}\n"
            report += f"  Reason: {resource['reason']}\n"
            report += f"  Action: {resource['recommendation']}\n"
            if resource.get('potential_savings'):
                report += f"  Savings: ${resource['potential_savings']:,.2f}/month\n"
            report += "\n"
    
    if analysis['oversized_resources']:
        report += f"\n\nOVERSIZED RESOURCES ({len(analysis['oversized_resources'])} found)\n"
        report += "=" * 40 + "\n"
        total_oversize_savings = sum(r.get('potential_savings', 0) for r in analysis['oversized_resources'])
        report += f"Total potential savings: ${total_oversize_savings:,.2f}/month\n\n"
        
        for resource in analysis['oversized_resources'][:10]:
            report += f"• {resource['type']} - {resource['resource_id']}\n"
            report += f"  Current: {resource['current_type']}\n"
            report += f"  Action: {resource['recommendation']}\n"
            report += f"  Savings: ${resource['potential_savings']:,.2f}/month\n\n"
    
    report += "\n\nFor detailed analysis and recommendations, please review the full report in the AWS console."
    
    return report