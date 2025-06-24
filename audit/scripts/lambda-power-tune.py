#!/usr/bin/env python3
"""
Lambda Performance Analysis and Power Tuning Script
Analyzes Lambda function performance and suggests optimal memory configurations
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from datetime import datetime
from datetime import timedelta

import boto3


class LambdaPowerTuner:
    def __init__(self, region: str = 'us-east-1'):
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.logs = boto3.client('logs', region_name=region)

    def get_all_functions(self) -> list[dict]:
        """Retrieve all Lambda functions in the account"""
        functions = []
        paginator = self.lambda_client.get_paginator('list_functions')

        for page in paginator.paginate():
            functions.extend(page['Functions'])

        return functions

    def analyze_function_performance(
        self,
        function_name: str,
        days: int = 7
    ) -> dict:
        """Analyze performance metrics for a specific function"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        metrics = {
            'function_name': function_name,
            'analysis_period': f'{days} days',
            'metrics': {}
        }

        # Define metrics to collect
        metric_queries = [
            {
                'Id': 'invocations',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Invocations',
                        'Dimensions': [
                            {'Name': 'FunctionName', 'Value': function_name}
                        ]
                    },
                    'Period': 3600,
                    'Stat': 'Sum'
                }
            },
            {
                'Id': 'duration',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Duration',
                        'Dimensions': [
                            {'Name': 'FunctionName', 'Value': function_name}
                        ]
                    },
                    'Period': 3600,
                    'Stat': 'Average'
                }
            },
            {
                'Id': 'errors',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Errors',
                        'Dimensions': [
                            {'Name': 'FunctionName', 'Value': function_name}
                        ]
                    },
                    'Period': 3600,
                    'Stat': 'Sum'
                }
            },
            {
                'Id': 'throttles',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'Throttles',
                        'Dimensions': [
                            {'Name': 'FunctionName', 'Value': function_name}
                        ]
                    },
                    'Period': 3600,
                    'Stat': 'Sum'
                }
            },
            {
                'Id': 'concurrent',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/Lambda',
                        'MetricName': 'ConcurrentExecutions',
                        'Dimensions': [
                            {'Name': 'FunctionName', 'Value': function_name}
                        ]
                    },
                    'Period': 3600,
                    'Stat': 'Maximum'
                }
            }
        ]

        # Get metrics data
        response = self.cloudwatch.get_metric_data(
            MetricDataQueries=metric_queries,
            StartTime=start_time,
            EndTime=end_time
        )

        # Process results
        for result in response['MetricDataResults']:
            metric_id = result['Id']
            values = result['Values']
            if values:
                metrics['metrics'][metric_id] = {
                    'average': sum(values) / len(values),
                    'max': max(values),
                    'min': min(values),
                    'total': sum(values) if metric_id in ['invocations', 'errors', 'throttles'] else None
                }

        # Get memory usage from CloudWatch Logs
        memory_usage = self._analyze_memory_usage(function_name, start_time, end_time)
        if memory_usage:
            metrics['memory_analysis'] = memory_usage

        return metrics

    def _analyze_memory_usage(
        self,
        function_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> dict:
        """Analyze memory usage patterns from CloudWatch Logs"""
        log_group_name = f'/aws/lambda/{function_name}'

        try:
            # Query for REPORT lines which contain memory usage
            query = r'''
            fields @timestamp, @message
            | filter @message like /REPORT/
            | parse @message /Memory Size: (?<memorySize>\d+) MB\s+Max Memory Used: (?<memoryUsed>\d+) MB/
            | stats avg(memoryUsed) as avg_memory_used,
                    max(memoryUsed) as max_memory_used,
                    min(memoryUsed) as min_memory_used,
                    count() as sample_count
            '''

            response = self.logs.start_query(
                logGroupName=log_group_name,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )

            query_id = response['queryId']

            # Wait for query to complete
            while True:
                result = self.logs.get_query_results(queryId=query_id)
                if result['status'] in ['Complete', 'Failed', 'Cancelled']:
                    break

            if result['status'] == 'Complete' and result['results']:
                stats = result['results'][0]
                return {
                    'avg_memory_used_mb': float(next(r['value'] for r in stats if r['field'] == 'avg_memory_used')),
                    'max_memory_used_mb': float(next(r['value'] for r in stats if r['field'] == 'max_memory_used')),
                    'min_memory_used_mb': float(next(r['value'] for r in stats if r['field'] == 'min_memory_used')),
                    'sample_count': int(next(r['value'] for r in stats if r['field'] == 'sample_count'))
                }
        except Exception as e:
            print(f"Error analyzing memory for {function_name}: {e}")

        return None

    def suggest_memory_optimization(
        self,
        function_config: dict,
        performance_data: dict
    ) -> dict:
        """Suggest optimal memory configuration based on analysis"""
        current_memory = function_config.get('MemorySize', 128)
        suggestions = {'function_name': function_config['FunctionName']}

        if 'memory_analysis' in performance_data:
            avg_used = performance_data['memory_analysis']['avg_memory_used_mb']
            max_used = performance_data['memory_analysis']['max_memory_used_mb']

            # Calculate optimal memory (with buffer)
            optimal_memory = int(max_used * 1.2)  # 20% buffer
            optimal_memory = max(128, min(10240, optimal_memory))  # Lambda limits

            # Round to nearest valid memory size
            valid_sizes = [128, 192, 256, 320, 384, 448, 512, 576, 640, 704, 768,
                          832, 896, 960, 1024, 1088, 1152, 1216, 1280, 1344, 1408,
                          1472, 1536, 1600, 1664, 1728, 1792, 1856, 1920, 1984,
                          2048, 2112, 2176, 2240, 2304, 2368, 2432, 2496, 2560,
                          2624, 2688, 2752, 2816, 2880, 2944, 3008, 3072, 3136,
                          3200, 3264, 3328, 3392, 3456, 3520, 3584, 3648, 3712,
                          3776, 3840, 3904, 3968, 4032, 4096, 4160, 4224, 4288,
                          4352, 4416, 4480, 4544, 4608, 4672, 4736, 4800, 4864,
                          4928, 4992, 5056, 5120, 5184, 5248, 5312, 5376, 5440,
                          5504, 5568, 5632, 5696, 5760, 5824, 5888, 5952, 6016,
                          6080, 6144, 6208, 6272, 6336, 6400, 6464, 6528, 6592,
                          6656, 6720, 6784, 6848, 6912, 6976, 7040, 7104, 7168,
                          7232, 7296, 7360, 7424, 7488, 7552, 7616, 7680, 7744,
                          7808, 7872, 7936, 8000, 8064, 8128, 8192, 8256, 8320,
                          8384, 8448, 8512, 8576, 8640, 8704, 8768, 8832, 8896,
                          8960, 9024, 9088, 9152, 9216, 9280, 9344, 9408, 9472,
                          9536, 9600, 9664, 9728, 9792, 9856, 9920, 9984, 10048,
                          10112, 10176, 10240]

            optimal_memory = min(valid_sizes, key=lambda x: abs(x - optimal_memory))

            suggestions.update({
                'current_memory_mb': current_memory,
                'optimal_memory_mb': optimal_memory,
                'potential_savings_percent': ((current_memory - optimal_memory) / current_memory * 100) if optimal_memory < current_memory else 0,
                'recommendation': 'DECREASE' if optimal_memory < current_memory else 'INCREASE' if optimal_memory > current_memory else 'OPTIMAL',
                'avg_memory_used_mb': avg_used,
                'max_memory_used_mb': max_used,
                'memory_utilization_percent': (max_used / current_memory * 100)
            })

            # Estimate cost impact
            if 'metrics' in performance_data and 'invocations' in performance_data['metrics']:
                invocations = performance_data['metrics']['invocations'].get('total', 0)
                duration_ms = performance_data['metrics']['duration'].get('average', 0)

                # Lambda pricing (approximate)
                price_per_gb_second = 0.0000166667
                current_cost = (current_memory / 1024) * (duration_ms / 1000) * invocations * price_per_gb_second
                optimal_cost = (optimal_memory / 1024) * (duration_ms / 1000) * invocations * price_per_gb_second

                suggestions['cost_analysis'] = {
                    'estimated_current_cost': round(current_cost, 4),
                    'estimated_optimal_cost': round(optimal_cost, 4),
                    'potential_savings': round(current_cost - optimal_cost, 4)
                }

        return suggestions

    def generate_report(self, output_dir: str = 'audit/reports'):
        """Generate comprehensive performance report for all functions"""
        os.makedirs(output_dir, exist_ok=True)

        functions = self.get_all_functions()
        results = []

        print(f"Analyzing {len(functions)} Lambda functions...")

        # Analyze functions in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_function = {
                executor.submit(
                    self.analyze_function_performance,
                    func['FunctionName']
                ): func for func in functions
            }

            for future in as_completed(future_to_function):
                func = future_to_function[future]
                try:
                    perf_data = future.result()
                    optimization = self.suggest_memory_optimization(func, perf_data)
                    results.append(optimization)
                except Exception as e:
                    print(f"Error analyzing {func['FunctionName']}: {e}")

        # Generate HTML report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(output_dir, f'lambda-performance-{timestamp}.html')

        self._generate_html_report(results, report_file)
        print(f"Report generated: {report_file}")

        # Also save raw data as JSON
        json_file = os.path.join(output_dir, f'lambda-performance-{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)

        return report_file

    def _generate_html_report(self, results: list[dict], output_file: str):
        """Generate HTML report with visualizations"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Lambda Performance Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .decrease { color: green; font-weight: bold; }
                .increase { color: orange; font-weight: bold; }
                .optimal { color: blue; font-weight: bold; }
                .summary { background-color: #f0f0f0; padding: 15px; margin: 20px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>Lambda Performance Analysis Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Total Functions Analyzed: {total_functions}</p>
                <p>Functions Needing Optimization: {need_optimization}</p>
                <p>Potential Total Savings: ${total_savings:.2f}</p>
            </div>
            
            <h2>Detailed Analysis</h2>
            <table>
                <tr>
                    <th>Function Name</th>
                    <th>Current Memory (MB)</th>
                    <th>Optimal Memory (MB)</th>
                    <th>Memory Utilization %</th>
                    <th>Recommendation</th>
                    <th>Potential Savings</th>
                </tr>
                {table_rows}
            </table>
            
            <p><small>Generated on: {timestamp}</small></p>
        </body>
        </html>
        """

        # Calculate summary statistics
        total_functions = len(results)
        need_optimization = sum(1 for r in results if r.get('recommendation') != 'OPTIMAL')
        total_savings = sum(r.get('cost_analysis', {}).get('potential_savings', 0) for r in results)

        # Generate table rows
        table_rows = []
        for result in sorted(results, key=lambda x: x.get('cost_analysis', {}).get('potential_savings', 0), reverse=True):
            recommendation_class = result.get('recommendation', '').lower()
            savings = result.get('cost_analysis', {}).get('potential_savings', 0)

            row = f"""
                <tr>
                    <td>{result['function_name']}</td>
                    <td>{result.get('current_memory_mb', 'N/A')}</td>
                    <td>{result.get('optimal_memory_mb', 'N/A')}</td>
                    <td>{result.get('memory_utilization_percent', 0):.1f}%</td>
                    <td class="{recommendation_class}">{result.get('recommendation', 'N/A')}</td>
                    <td>${savings:.4f}</td>
                </tr>
            """
            table_rows.append(row)

        # Generate final HTML
        html_content = html_template.format(
            total_functions=total_functions,
            need_optimization=need_optimization,
            total_savings=total_savings,
            table_rows=''.join(table_rows),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        with open(output_file, 'w') as f:
            f.write(html_content)

if __name__ == '__main__':
    tuner = LambdaPowerTuner()
    tuner.generate_report()
