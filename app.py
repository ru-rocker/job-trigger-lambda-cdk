#!/usr/bin/env python3

from aws_cdk import core

from job_trigger_lambda.job_trigger_lambda_stack import JobTriggerLambdaStack


app = core.App()
JobTriggerLambdaStack(app, "job-trigger-lambda", env={'region': 'ap-southeast-1'})

app.synth()
