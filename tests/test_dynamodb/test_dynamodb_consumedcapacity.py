import boto3
import pytest
from botocore.exceptions import ClientError

from moto import mock_aws


@mock_aws
def test_error_on_wrong_value_for_consumed_capacity():
    resource = boto3.resource("dynamodb", region_name="ap-northeast-3")
    client = boto3.client("dynamodb", region_name="ap-northeast-3")
    client.create_table(
        TableName="jobs",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )

    table = resource.Table("jobs")
    item = {"job_id": "asdasdasd", "expires_at": "1"}

    # PUT_ITEM
    with pytest.raises(ClientError) as ex:
        table.put_item(Item=item, ReturnConsumedCapacity="Garbage")
    err = ex.value.response["Error"]
    assert err["Code"] == "ValidationException"
    assert (
        err["Message"]
        == "1 validation error detected: Value 'Garbage' at 'returnConsumedCapacity' failed to satisfy constraint: Member must satisfy enum value set: [INDEXES, TOTAL, NONE]"
    )


@mock_aws
def test_consumed_capacity_get_unknown_item():
    conn = boto3.client("dynamodb", region_name="us-east-1")
    conn.create_table(
        TableName="test_table",
        KeySchema=[{"AttributeName": "u", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "u", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    response = conn.get_item(
        TableName="test_table",
        Key={"u": {"S": "does_not_exist"}},
        ReturnConsumedCapacity="TOTAL",
    )

    # Should still return ConsumedCapacity, even if it does not return an item
    assert response["ConsumedCapacity"] == {
        "TableName": "test_table",
        "CapacityUnits": 0.5,
    }


@mock_aws
@pytest.mark.parametrize(
    "capacity,should_have_capacity,should_have_table",
    [
        [None, False, False],
        ["NONE", False, False],
        ["TOTAL", True, False],
        ["INDEXES", True, True],
    ],
)
def test_only_return_consumed_capacity_when_required(
    capacity, should_have_capacity, should_have_table
):
    resource = boto3.resource("dynamodb", region_name="ap-northeast-3")
    client = boto3.client("dynamodb", region_name="ap-northeast-3")
    client.create_table(
        TableName="jobs",
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        LocalSecondaryIndexes=[
            {
                "IndexName": "job_name-index",
                "KeySchema": [{"AttributeName": "job_name", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "job_name", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )

    table = resource.Table("jobs")
    item = {"job_id": "asdasdasd", "expires_at": "1"}

    # PUT_ITEM
    args = {"Item": item}
    if capacity:
        args["ReturnConsumedCapacity"] = capacity
    response = table.put_item(**args)
    validate_response(response, should_have_capacity, should_have_table)

    # GET_ITEM
    args = {"Key": {"job_id": item["job_id"]}}
    if capacity:
        args["ReturnConsumedCapacity"] = capacity
    response = table.get_item(**args)
    validate_response(response, should_have_capacity, should_have_table, value=0.5)

    # SCAN
    args = {"TableName": "jobs"}
    if capacity:
        args["ReturnConsumedCapacity"] = capacity
    response = client.scan(**args)
    validate_response(response, should_have_capacity, should_have_table)

    # SCAN_INDEX
    args["IndexName"] = "job_name-index"
    response = client.scan(**args)
    validate_response(response, should_have_capacity, should_have_table, is_index=True)

    # QUERY
    args = {
        "TableName": "jobs",
        "KeyConditionExpression": "job_id = :id",
        "ExpressionAttributeValues": {":id": {"S": "asdasdasd"}},
    }
    if capacity:
        args["ReturnConsumedCapacity"] = capacity
    response = client.query(**args)
    validate_response(response, should_have_capacity, should_have_table)

    # QUERY_INDEX
    args["IndexName"] = "job_name-index"
    args["KeyConditionExpression"] = "job_name = :id"
    response = client.query(**args)
    validate_response(response, should_have_capacity, should_have_table, is_index=True)


def validate_response(
    response, should_have_capacity, should_have_table, is_index=False, value=1.0
):
    if should_have_capacity:
        capacity = response["ConsumedCapacity"]
        assert capacity["TableName"] == "jobs"
        assert capacity["CapacityUnits"] == value
        if should_have_table:
            assert capacity["Table"] == {"CapacityUnits": value}
            if is_index:
                assert capacity["LocalSecondaryIndexes"] == {
                    "job_name-index": {"CapacityUnits": value}
                }
    else:
        assert "ConsumedCapacity" not in response
