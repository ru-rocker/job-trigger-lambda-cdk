from aws_cdk import (
    core,
    aws_lambda as _lambda,
    aws_ec2 as _ec2,
    aws_iam as _iam,
    aws_ssm as _ssm,
    aws_events as _events,
    aws_events_targets as _et,
    aws_cloudwatch as _cw,
    aws_logs as _logs,
    aws_sns as _sns,
    aws_sns_subscriptions as _subs,
    aws_cloudwatch_actions as _cw_act,
)
from aws_cdk.aws_ec2 import Vpc
import random
import string


class JobTriggerLambdaStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get VPC
        vpc = Vpc.from_vpc_attributes(
            self,
            id='vpc-dev',
            vpc_id='YOUR_VPC_ID',
            availability_zones=core.Fn.get_azs(),
            private_subnet_ids=[
                'YOUR_PRIVATE_SUBNET_ID1', 'YOUR_PRIVATE_SUBNET_ID2', 'YOUR_PRIVATE_SUBNET_ID2'],
            private_subnet_route_table_ids=[
                'YOUR_PRIVATE_ROUTE_TABLE_ID1', 'YOUR_PRIVATE_ROUTE_TABLE_ID2', 'YOUR_PRIVATE_ROUTE_TABLE_ID3']
        )

        # Create lambda
        my_lambda = _lambda.Function(
            self, 'testLambdaVPC_CDK',
            function_name='CDK_test_job_trigger_lambda_vpc',
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=_lambda.Code.asset('lambda'),
            handler='testLambdaVPC_CDK.handler',
            vpc=vpc,
            log_retention=_logs.RetentionDays.THREE_DAYS,
        )
        core.Tags.of(my_lambda).add('src.projectKey', 'job-scheduler-poc')
        my_lambda.add_to_role_policy(
            _iam.PolicyStatement(
                effect=_iam.Effect.ALLOW,
                actions=[
                    "ssm:Describe*",
                    "ssm:Get*",
                    "ssm:List*"
                ],
                resources=["*"],
            )
        )

        # Create SNS
        topic = _sns.Topic(
            self,
            "JobTriggerSNS_POC",
            topic_name="CDK_JobTriggerSNS_POC",
        )
        core.Tags.of(topic).add('src.projectKey', 'job-scheduler-poc')
        topic.add_subscription(_subs.EmailSubscription(
            email_address='ricky.martaputra@gmail.com'))

        # Create cloudwatch events
        rule = _events.Rule(
            self,
            id='event-trigger',
            schedule=_events.Schedule.rate(core.Duration.minutes(1))
        )
        rule.add_target(target=_et.LambdaFunction(my_lambda))

        _ssm.StringParameter(self,
                             id="API_KEY",
                             string_value=''.join(random.choice(
                                 string.ascii_uppercase + string.digits) for _ in range(32)),
                             parameter_name="/job-trigger-lambda/api_key",
                             )

        # Create Dashboard
        dashboard = _cw.Dashboard(
            self,
            id='JobTriggerLambdaDashboard',
            dashboard_name='JobTriggerLambdaDashboard',
        )

        # Duration Widget
        duration_widget = _cw.GraphWidget(
            title='Lambda Duration',
            width=12,
        )
        duration_metrics = _cw.Metric(
            namespace='AWS/Lambda',
            metric_name='Duration',
            dimensions={
                'FunctionName': my_lambda.function_name
            },
            statistic='p99.00',
            period=core.Duration.seconds(60),
        )
        duration_widget.add_left_metric(duration_metrics)

        # stats widgets
        invocation_metric = _cw.Metric(
            namespace='AWS/Lambda',
            metric_name='Invocations',
            dimensions={
                'FunctionName': my_lambda.function_name
            },
            statistic='sum',
            period=core.Duration.seconds(60),
        )

        throttle_metric = _cw.Metric(
            namespace='AWS/Lambda',
            metric_name='Throttles',
            dimensions={
                'FunctionName': my_lambda.function_name
            },
            statistic='sum',
            period=core.Duration.seconds(60),
        )

        concurrent_metric = _cw.Metric(
            namespace='AWS/Lambda',
            metric_name='Concurrent',
            dimensions={
                'FunctionName': my_lambda.function_name
            },
            statistic='sum',
            period=core.Duration.seconds(60),
        )

        error_metric = _cw.Metric(
            namespace='AWS/Lambda',
            metric_name='Errors',
            dimensions={
                'FunctionName': my_lambda.function_name
            },
            statistic='sum',
            period=core.Duration.minutes(5),
        )

        stats_widget = _cw.SingleValueWidget(
            title='Lambda Invocation, Throttle, Concurrent and Error',
            width=12,
            height=6,
            metrics=[invocation_metric, throttle_metric,
                     concurrent_metric, error_metric]
        )

        # job status widget
        job_status_metrics = _cw.Metric(
            namespace='job-scheduler-poc',
            metric_name='JOB_STATUS',
            dimensions={
                'JOB_LATENCY': 'RandomMessageProcessor'
            },
            statistic='sum',
            period=core.Duration.seconds(60),
        )

        job_status_widget = _cw.SingleValueWidget(
            title='Job Status',
            width=4,
            height=6,
            metrics=[job_status_metrics]
        )

        # job latency widget
        job_latency_metrics = _cw.Metric(
            namespace='job-scheduler-poc',
            metric_name='JOB_LATENCY',
            dimensions={
                'JOB_LATENCY': 'RandomMessageProcessor'
            },
            statistic='p99',
            period=core.Duration.minutes(5)
        )

        job_latency_widget = _cw.GraphWidget(
            title='Job Latency',
            width=20,
            stacked=True,
        )
        job_latency_widget.add_left_metric(job_latency_metrics)

        dashboard.add_widgets(job_status_widget, job_latency_widget)
        dashboard.add_widgets(duration_widget, stats_widget)

        # alarm: duration
        duration_anomaly_cfnalarm = _cw.CfnAlarm(
            self,
            "DurationAnomalyAlarm",
            actions_enabled=True,
            alarm_actions=[topic.topic_arn],
            alarm_name="CDK_DurationAnomalyAlarm",
            comparison_operator="GreaterThanUpperThreshold",
            datapoints_to_alarm=2,
            evaluation_periods=2,
            metrics=[
                _cw.CfnAlarm.MetricDataQueryProperty(
                    expression="ANOMALY_DETECTION_BAND(m1, 2)",
                    id="ad1"
                ),
                _cw.CfnAlarm.MetricDataQueryProperty(
                    id="m1",
                    metric_stat=_cw.CfnAlarm.MetricStatProperty(
                        metric=_cw.CfnAlarm.MetricProperty(
                            metric_name='Duration',
                            namespace='AWS/Lambda',
                            dimensions=[_cw.CfnAlarm.DimensionProperty(
                                name='FunctionName', value=my_lambda.function_name)],
                        ),
                        period=core.Duration.minutes(5).to_seconds(),
                        stat="p99.00"
                    )
                )
            ],
            ok_actions=[topic.topic_arn],
            threshold_metric_id="ad1",
            treat_missing_data="missing",
        )

        # alarm: error lambda
        error_lambda_alarm = error_metric.create_alarm(
            self,
            id="ErrorLambdaAlarm",
            alarm_name="CDK_ErrorLambdaAlarm",
            treat_missing_data=_cw.TreatMissingData.MISSING,
            datapoints_to_alarm=2,
            comparison_operator=_cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            threshold=1,
            evaluation_periods=2,
            statistic='avg',
        )
        error_lambda_alarm.add_alarm_action(_cw_act.SnsAction(topic=topic))
        error_lambda_alarm.add_ok_action(_cw_act.SnsAction(topic=topic))

        # alarm: job_status
        job_status_alarm = job_status_metrics.create_alarm(
            self,
            id="JobStatusAlarm",
            alarm_name="CDK_JobStatusAlarm",
            treat_missing_data=_cw.TreatMissingData.MISSING,
            datapoints_to_alarm=2,
            comparison_operator=_cw.ComparisonOperator.LESS_THAN_THRESHOLD,
            threshold=1,
            evaluation_periods=2,
            statistic='avg',
        )
        job_status_alarm.add_alarm_action(_cw_act.SnsAction(topic=topic))
        job_status_alarm.add_ok_action(_cw_act.SnsAction(topic=topic))

        # alarm: job_latency
        job_latency_anomaly_cfnalarm = _cw.CfnAlarm(
            self,
            "JobLatencyAnomalyAlarm",
            actions_enabled=True,
            alarm_actions=[topic.topic_arn],
            alarm_name="CDK_JobLatencyAnomalyAlarm",
            comparison_operator="GreaterThanUpperThreshold",
            datapoints_to_alarm=2,
            evaluation_periods=2,
            metrics=[
                _cw.CfnAlarm.MetricDataQueryProperty(
                    expression="ANOMALY_DETECTION_BAND(m1, 2)",
                    id="ad1"
                ),
                _cw.CfnAlarm.MetricDataQueryProperty(
                    id="m1",
                    metric_stat=_cw.CfnAlarm.MetricStatProperty(
                        metric=_cw.CfnAlarm.MetricProperty(
                            namespace='job-scheduler-poc',
                            metric_name='JOB_LATENCY',
                            dimensions=[_cw.CfnAlarm.DimensionProperty(
                                name='JOB_LATENCY', value='RandomMessageProcessor')],
                        ),
                        period=core.Duration.minutes(5).to_seconds(),
                        stat="p99.00"
                    )
                )
            ],
            ok_actions=[topic.topic_arn],
            threshold_metric_id="ad1",
            treat_missing_data="missing",
        )
