import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime, timezone
from decimal import Decimal
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from collector.enhanced_main import AWSInventoryCollector


class TestAWSInventoryCollector(unittest.TestCase):
    """Unit tests for enhanced AWS Inventory Collector"""
    
    @patch('collector.enhanced_main.boto3.resource')
    def setUp(self, mock_boto_resource):
        """Set up test fixtures"""
        # Mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_table = Mock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        
        self.collector = AWSInventoryCollector(table_name='test-inventory')
        self.collector.accounts = {
            'test-account': {
                'account_id': '123456789012',
                'role_name': 'TestRole'
            }
        }
    
    @patch('collector.enhanced_main.boto3.client')
    def test_assume_role_success(self, mock_boto_client):
        """Test successful role assumption"""
        # Mock STS client
        mock_sts = Mock()
        mock_boto_client.return_value = mock_sts
        
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'test-key',
                'SecretAccessKey': 'test-secret',
                'SessionToken': 'test-token'
            }
        }
        
        # Test assume role
        with patch('collector.enhanced_main.boto3.Session') as mock_session:
            session = self.collector.assume_role('123456789012', 'TestRole')
            
            # Verify STS was called correctly
            mock_sts.assume_role.assert_called_once()
            call_args = mock_sts.assume_role.call_args[1]
            self.assertEqual(call_args['RoleArn'], 'arn:aws:iam::123456789012:role/TestRole')
            self.assertEqual(call_args['ExternalId'], 'inventory-collector')
    
    @patch('collector.enhanced_main.boto3.client')
    def test_assume_role_retry(self, mock_boto_client):
        """Test role assumption with retry logic"""
        from botocore.exceptions import ClientError
        
        mock_sts = Mock()
        mock_boto_client.return_value = mock_sts
        
        # First call fails, second succeeds
        mock_sts.assume_role.side_effect = [
            ClientError({'Error': {'Code': 'Throttling'}}, 'AssumeRole'),
            {
                'Credentials': {
                    'AccessKeyId': 'test-key',
                    'SecretAccessKey': 'test-secret',
                    'SessionToken': 'test-token'
                }
            }
        ]
        
        with patch('time.sleep'):  # Don't actually sleep in tests
            with patch('collector.enhanced_main.boto3.Session'):
                session = self.collector.assume_role('123456789012', 'TestRole')
                
                # Verify retry happened
                self.assertEqual(mock_sts.assume_role.call_count, 2)
    
    def test_estimate_ec2_cost(self):
        """Test EC2 cost estimation"""
        # Running instance
        instance = {
            'InstanceType': 't3.medium',
            'State': {'Name': 'running'}
        }
        cost = self.collector.estimate_ec2_cost(instance)
        expected = 0.0416 * 24 * 30  # t3.medium hourly rate * hours/month
        self.assertAlmostEqual(cost, expected, places=2)
        
        # Stopped instance
        instance['State']['Name'] = 'stopped'
        cost = self.collector.estimate_ec2_cost(instance)
        self.assertEqual(cost, 0.0)
        
        # Unknown instance type
        instance['InstanceType'] = 'unknown.type'
        instance['State']['Name'] = 'running'
        cost = self.collector.estimate_ec2_cost(instance)
        expected = 0.05 * 24 * 30  # default rate
        self.assertAlmostEqual(cost, expected, places=2)
    
    def test_estimate_rds_cost(self):
        """Test RDS cost estimation"""
        instance = {
            'DBInstanceClass': 'db.t3.micro',
            'DBInstanceStatus': 'available'
        }
        cost = self.collector.estimate_rds_cost(instance)
        expected = 0.017 * 24 * 30
        self.assertAlmostEqual(cost, expected, places=2)
        
        # Not available
        instance['DBInstanceStatus'] = 'stopped'
        cost = self.collector.estimate_rds_cost(instance)
        self.assertEqual(cost, 0.0)
    
    def test_estimate_s3_cost(self):
        """Test S3 cost estimation"""
        # 100 GB standard storage
        metrics = {
            'size_bytes': 100 * 1024**3,
            'storage_class': 'standard'
        }
        cost = self.collector.estimate_s3_cost(metrics)
        expected = 100 * 0.023  # 100 GB * $0.023 per GB
        self.assertAlmostEqual(cost, expected, places=2)
        
        # Glacier storage
        metrics['storage_class'] = 'glacier'
        cost = self.collector.estimate_s3_cost(metrics)
        expected = 100 * 0.004
        self.assertAlmostEqual(cost, expected, places=2)
    
    @patch('collector.enhanced_main.boto3.Session')
    def test_collect_ec2_instances(self, mock_session_class):
        """Test EC2 instance collection"""
        # Mock session and EC2 client
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_ec2 = Mock()
        mock_session.client.return_value = mock_ec2
        
        # Mock paginator
        mock_paginator = Mock()
        mock_ec2.get_paginator.return_value = mock_paginator
        
        # Mock EC2 response
        mock_paginator.paginate.return_value = [
            {
                'Reservations': [
                    {
                        'Instances': [
                            {
                                'InstanceId': 'i-1234567890abcdef0',
                                'InstanceType': 't3.micro',
                                'State': {'Name': 'running'},
                                'LaunchTime': datetime.now(timezone.utc),
                                'VpcId': 'vpc-12345',
                                'SubnetId': 'subnet-12345',
                                'PublicIpAddress': '1.2.3.4',
                                'PrivateIpAddress': '10.0.0.1',
                                'Tags': [
                                    {'Key': 'Name', 'Value': 'TestInstance'},
                                    {'Key': 'Environment', 'Value': 'Test'}
                                ],
                                'SecurityGroups': [{'GroupId': 'sg-12345'}]
                            }
                        ]
                    }
                ]
            }
        ]
        
        # Collect instances
        resources = self.collector.collect_ec2_instances(
            mock_session, 'us-east-1', '123456789012', 'test-account'
        )
        
        # Verify results
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource['resource_type'], 'ec2_instance')
        self.assertEqual(resource['resource_id'], 'i-1234567890abcdef0')
        self.assertEqual(resource['attributes']['instance_type'], 't3.micro')
        self.assertEqual(resource['attributes']['tags']['Name'], 'TestInstance')
        self.assertGreater(resource['estimated_monthly_cost'], 0)
    
    @patch('collector.enhanced_main.boto3.Session')
    def test_collect_s3_buckets(self, mock_session_class):
        """Test S3 bucket collection"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_s3 = Mock()
        mock_cloudwatch = Mock()
        
        def client_side_effect(service, **kwargs):
            if service == 's3':
                return mock_s3
            elif service == 'cloudwatch':
                return mock_cloudwatch
            return Mock()
        
        mock_session.client.side_effect = client_side_effect
        
        # Mock S3 responses
        mock_s3.list_buckets.return_value = {
            'Buckets': [
                {
                    'Name': 'test-bucket',
                    'CreationDate': datetime.now(timezone.utc)
                }
            ]
        }
        
        mock_s3.get_bucket_location.return_value = {
            'LocationConstraint': 'us-west-2'
        }
        
        mock_s3.get_bucket_versioning.return_value = {
            'Status': 'Enabled'
        }
        
        mock_s3.get_bucket_encryption.return_value = {
            'ServerSideEncryptionConfiguration': {}
        }
        
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'Environment', 'Value': 'Test'}
            ]
        }
        
        mock_s3.get_bucket_acl.return_value = {
            'Grants': []
        }
        
        # Mock CloudWatch metrics
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Average': 1024**3}  # 1 GB
            ]
        }
        
        # Collect buckets
        resources = self.collector.collect_s3_buckets(
            mock_session, '123456789012', 'test-account'
        )
        
        # Verify results
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource['resource_type'], 's3_bucket')
        self.assertEqual(resource['resource_id'], 'test-bucket')
        self.assertEqual(resource['region'], 'us-west-2')
        self.assertEqual(resource['attributes']['versioning'], 'Enabled')
        self.assertTrue(resource['attributes']['encryption'])
        self.assertEqual(resource['attributes']['size_gb'], 1.0)
        self.assertFalse(resource['attributes']['public_access'])
    
    @patch('collector.enhanced_main.boto3.Session')
    def test_collect_lambda_functions(self, mock_session_class):
        """Test Lambda function collection"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_lambda = Mock()
        mock_cloudwatch = Mock()
        
        def client_side_effect(service, **kwargs):
            if service == 'lambda':
                return mock_lambda
            elif service == 'cloudwatch':
                return mock_cloudwatch
            return Mock()
        
        mock_session.client.side_effect = client_side_effect
        
        # Mock Lambda responses
        mock_paginator = Mock()
        mock_lambda.get_paginator.return_value = mock_paginator
        
        mock_paginator.paginate.return_value = [
            {
                'Functions': [
                    {
                        'FunctionName': 'test-function',
                        'FunctionArn': 'arn:aws:lambda:us-east-1:123456789012:function:test-function',
                        'Runtime': 'python3.9',
                        'Handler': 'index.handler',
                        'CodeSize': 1024,
                        'MemorySize': 256,
                        'Timeout': 60,
                        'LastModified': '2023-01-01T00:00:00Z',
                        'Description': 'Test function',
                        'Role': 'arn:aws:iam::123456789012:role/lambda-role',
                        'Tags': {'Environment': 'Test'}
                    }
                ]
            }
        ]
        
        # Mock CloudWatch metrics
        mock_cloudwatch.get_metric_statistics.side_effect = [
            {'Datapoints': [{'Sum': 1000}]},  # Invocations
            {'Datapoints': [{'Sum': 10}]}     # Errors
        ]
        
        # Collect functions
        resources = self.collector.collect_lambda_functions(
            mock_session, 'us-east-1', '123456789012', 'test-account'
        )
        
        # Verify results
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource['resource_type'], 'lambda_function')
        self.assertEqual(resource['attributes']['function_name'], 'test-function')
        self.assertEqual(resource['attributes']['invocations_30d'], 1000)
        self.assertEqual(resource['attributes']['errors_30d'], 10)
        self.assertEqual(resource['attributes']['error_rate'], 1.0)
        # Lambda cost can be very small, just ensure it's non-negative
        self.assertGreaterEqual(resource['estimated_monthly_cost'], 0)
    
    @patch('collector.enhanced_main.boto3.resource')
    def test_save_to_dynamodb(self, mock_boto_resource):
        """Test saving to DynamoDB with type conversion"""
        # Mock DynamoDB
        mock_dynamodb = Mock()
        mock_table = Mock()
        mock_batch_writer = Mock()
        
        mock_boto_resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        
        # Create a proper mock for context manager
        mock_batch_context = MagicMock()
        mock_batch_context.__enter__.return_value = mock_batch_writer
        mock_table.batch_writer.return_value = mock_batch_context
        
        # Test data with various types
        resources = [
            {
                'resource_type': 'ec2_instance',
                'resource_id': 'i-12345',
                'account_id': '123456789012',
                'account_name': 'test-account',
                'region': 'us-east-1',
                'timestamp': '2023-01-01T00:00:00Z',
                'estimated_monthly_cost': 123.45,  # Float to be converted
                'attributes': {
                    'state': 'running',
                    'cpu_utilization': 45.67,  # Nested float
                    'tags': {
                        'Name': 'Test',
                        'Cost': 12.34  # Another nested float
                    }
                }
            }
        ]
        
        # Create a new collector instance with the mocked table
        collector = AWSInventoryCollector(table_name='test-inventory')
        collector.table = mock_table
        
        # Save resources
        collector.save_to_dynamodb(resources)
        
        # Verify batch writer was called
        mock_batch_writer.put_item.assert_called_once()
        
        # Check that floats were converted to Decimal
        call_args = mock_batch_writer.put_item.call_args[1]['Item']
        self.assertIsInstance(call_args['estimated_monthly_cost'], Decimal)
        self.assertIsInstance(call_args['attributes']['cpu_utilization'], Decimal)
        self.assertIsInstance(call_args['attributes']['tags']['Cost'], Decimal)


class TestInventoryQuery(unittest.TestCase):
    """Unit tests for enhanced inventory query"""
    
    @patch('query.enhanced_inventory_query.boto3.resource')
    def setUp(self, mock_boto_resource):
        """Set up test fixtures"""
        from query.enhanced_inventory_query import InventoryQuery
        
        self.mock_table = Mock()
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = self.mock_table
        mock_boto_resource.return_value = mock_dynamodb
        
        self.query = InventoryQuery(table_name='test-inventory')
    
    def test_decimal_to_float_conversion(self):
        """Test Decimal to float conversion"""
        test_data = {
            'cost': Decimal('123.45'),
            'nested': {
                'value': Decimal('67.89'),
                'list': [Decimal('1.23'), Decimal('4.56')]
            }
        }
        
        result = self.query._decimal_to_float(test_data)
        
        self.assertEqual(result['cost'], 123.45)
        self.assertEqual(result['nested']['value'], 67.89)
        self.assertEqual(result['nested']['list'], [1.23, 4.56])
    
    def test_get_summary(self):
        """Test summary generation"""
        # Mock scan response
        self.mock_table.scan.return_value = {
            'Items': [
                {
                    'resource_type': 'ec2_instance',
                    'account_name': 'production',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('100.00')
                },
                {
                    'resource_type': 'rds_instance',
                    'account_name': 'production',
                    'region': 'us-west-2',
                    'estimated_monthly_cost': Decimal('200.00')
                },
                {
                    'resource_type': 'ec2_instance',
                    'account_name': 'development',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('50.00')
                }
            ]
        }
        
        summary = self.query.get_summary()
        
        # Verify summary
        self.assertEqual(summary['total_resources'], 3)
        self.assertEqual(summary['by_type']['ec2_instance'], 2)
        self.assertEqual(summary['by_type']['rds_instance'], 1)
        self.assertEqual(summary['by_account']['production'], 2)
        self.assertEqual(summary['by_account']['development'], 1)
        self.assertEqual(summary['total_monthly_cost'], 350.00)
        self.assertEqual(summary['cost_by_type']['ec2_instance'], 150.00)
        self.assertEqual(summary['cost_by_type']['rds_instance'], 200.00)
    
    def test_cost_analysis(self):
        """Test cost analysis with optimization opportunities"""
        # Mock scan response with various resource states
        self.mock_table.scan.return_value = {
            'Items': [
                {
                    'resource_type': 'ec2_instance',
                    'resource_id': 'i-stopped',
                    'account_name': 'test',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('0'),
                    'attributes': {
                        'state': 'stopped',
                        'launch_time': '2020-01-01T00:00:00Z',
                        'instance_type': 't3.micro'
                    }
                },
                {
                    'resource_type': 'ec2_instance',
                    'resource_id': 'i-oversized',
                    'account_name': 'test',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('500.00'),
                    'attributes': {
                        'state': 'running',
                        'instance_type': 'm5.4xlarge'
                    }
                },
                {
                    'resource_type': 'rds_instance',
                    'resource_id': 'db-unencrypted',
                    'account_name': 'test',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('200.00'),
                    'attributes': {
                        'storage_encrypted': False
                    }
                },
                {
                    'resource_type': 's3_bucket',
                    'resource_id': 'public-bucket',
                    'account_name': 'test',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('10.00'),
                    'attributes': {
                        'public_access': True,
                        'encryption': False
                    }
                },
                {
                    'resource_type': 'lambda_function',
                    'resource_id': 'unused-function',
                    'account_name': 'test',
                    'region': 'us-east-1',
                    'estimated_monthly_cost': Decimal('5.00'),
                    'attributes': {
                        'invocations_monthly': 5
                    }
                }
            ]
        }
        
        analysis = self.query.get_cost_analysis()
        
        # Verify analysis results
        self.assertEqual(analysis['total_monthly_cost'], 715.00)
        self.assertEqual(analysis['yearly_projection'], 715.00 * 12)
        
        # Check idle resources
        self.assertEqual(len(analysis['idle_resources']), 2)  # Stopped EC2 and unused Lambda
        idle_ids = [r['resource_id'] for r in analysis['idle_resources']]
        self.assertIn('i-stopped', idle_ids)
        self.assertIn('unused-function', idle_ids)
        
        # Check oversized resources
        self.assertEqual(len(analysis['oversized_resources']), 1)
        self.assertEqual(analysis['oversized_resources'][0]['resource_id'], 'i-oversized')
        self.assertAlmostEqual(
            analysis['oversized_resources'][0]['potential_savings'],
            500.00 * 0.3,  # 30% savings estimate
            places=2
        )
        
        # Check security issues
        self.assertEqual(len(analysis['unencrypted_resources']), 2)  # RDS and S3
        self.assertEqual(len(analysis['public_resources']), 1)  # S3 bucket
        
        unencrypted_ids = [r['resource_id'] for r in analysis['unencrypted_resources']]
        self.assertIn('db-unencrypted', unencrypted_ids)
        self.assertIn('public-bucket', unencrypted_ids)


class TestLambdaHandlers(unittest.TestCase):
    """Unit tests for Lambda handlers"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock environment variables
        os.environ['DYNAMODB_TABLE_NAME'] = 'test-inventory'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MONTHLY_COST_THRESHOLD'] = '4000'  # Set below test value to trigger alert
        os.environ['REPORT_BUCKET'] = 'test-reports-bucket'
    
    @patch('handler.AWSInventoryCollector')
    @patch('handler.send_notification')
    @patch('handler.send_metric')
    def test_handle_collection_success(self, mock_metrics, mock_sns, mock_collector_class):
        """Test successful inventory collection"""
        from handler import handle_collection
        
        # Mock collector
        mock_collector = Mock()
        mock_collector_class.return_value = mock_collector
        
        mock_collector.collect_inventory.return_value = [
            {
                'resource_type': 'ec2_instance',
                'resource_id': 'i-12345',
                'account_name': 'test',
                'estimated_monthly_cost': 100.00
            },
            {
                'resource_type': 'rds_instance',
                'resource_id': 'db-12345',
                'account_name': 'test',
                'estimated_monthly_cost': 200.00
            }
        ]
        mock_collector.failed_collections = []  # No failures
        
        # Test event
        event = {
            'accounts': {
                'test': {
                    'account_id': '123456789012',
                    'role_name': 'TestRole'
                }
            }
        }
        
        # Call handler
        result = handle_collection(event, {}, datetime.now(timezone.utc))
        
        # Verify response
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        self.assertEqual(body['message'], 'Collection completed successfully')
        self.assertEqual(body['resources_collected'], 2)
        
        # Verify metrics were sent (multiple calls expected)
        self.assertGreater(mock_metrics.call_count, 0)
        # Check that specific metrics were sent
        metric_calls = [call[0][0] for call in mock_metrics.call_args_list]
        self.assertIn('ResourcesCollected', metric_calls)
        self.assertIn('TotalMonthlyCost', metric_calls)
        
        # Verify no alerts sent (under threshold)
        mock_sns.assert_not_called()
    
    @patch('handler.InventoryQuery')
    @patch('handler.send_notification')
    @patch('handler.get_clients')
    def test_handle_cost_analysis(self, mock_get_clients, mock_sns, mock_query_class):
        """Test cost analysis handler"""
        from handler import handle_cost_analysis
        
        # Mock query
        mock_query = Mock()
        mock_query_class.return_value = mock_query
        
        mock_query.get_cost_analysis.return_value = {
            'total_monthly_cost': 5000.00,
            'yearly_projection': 60000.00,
            'total_potential_savings': 1000.00,
            'cost_by_type': {
                'ec2_instance': 3000.00,
                'rds_instance': 1500.00,
                's3_bucket': 500.00
            },
            'top_expensive_resources': [
                {
                    'resource_id': 'i-expensive',
                    'resource_type': 'ec2_instance',
                    'monthly_cost': 1000.00
                }
            ],
            'idle_resources': [{'resource_id': 'i-idle'}],
            'oversized_resources': [{'resource_id': 'i-big'}],
            'unencrypted_resources': [{'resource_id': 'db-unencrypted'}]
        }
        
        # Mock S3 and other clients
        mock_sns_client = Mock()
        mock_cloudwatch = Mock()
        mock_s3 = Mock()
        mock_get_clients.return_value = (mock_sns_client, mock_cloudwatch, mock_s3)
        
        # Test event with report request
        event = {'send_report': True}
        
        # Call handler
        result = handle_cost_analysis(event, {})
        
        # Verify response
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        self.assertEqual(body['total_monthly_cost'], 5000.00)
        self.assertEqual(body['message'], 'Cost analysis completed')
        
        # Verify notification was sent (cost 5000 exceeds threshold of 4000)
        mock_sns.assert_called_once()
        # send_notification is called with keyword arguments
        call_kwargs = mock_sns.call_args[1]
        self.assertIn('Cost Alert', call_kwargs['subject'])
        self.assertIn('5000', call_kwargs['message'])
        
        # Verify S3 upload
        mock_s3.put_object.assert_called_once()


if __name__ == '__main__':
    unittest.main()