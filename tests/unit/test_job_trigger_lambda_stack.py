import json
import pytest

from aws_cdk import core
from job_trigger_lambda.job_trigger_lambda_stack import JobTriggerLambdaStack


def get_template():
    app = core.App()
    JobTriggerLambdaStack(app, "job-trigger-lambda")
    return json.dumps(app.synth().get_stack("job-trigger-lambda").template)


def test_sqs_queue_created():
    assert("AWS::SQS::Queue" in get_template())


def test_sns_topic_created():
    assert("AWS::SNS::Topic" in get_template())
