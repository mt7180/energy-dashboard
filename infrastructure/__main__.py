import pulumi
import pulumi_aws as aws
from dotenv import load_dotenv
import os

load_dotenv(override=True)
config = pulumi.Config()

project_name = "rds-energy-dashboard"
aws_accout_id = aws.get_caller_identity().account_id
aws_region = aws.get_region()


# Setup the AWS provider to assume a specific role
assumed_role_provider = aws.Provider(
    "assumedRoleProvider",
    assume_role=aws.ProviderAssumeRoleArgs(
        role_arn=os.getenv("RDS_IAM_ROLE"),
        session_name="PulumiSession_rds",
    ),
    region=aws_region.name,
)

# Define a new VPC
vpc = aws.ec2.Vpc(
    "database_vpc",
    cidr_block="172.31.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Define a new subnet
subnet1 = aws.ec2.Subnet(
    "database_subnet1",
    cidr_block="172.31.0.0/20",
    availability_zone="eu-central-1a",
    vpc_id=vpc.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

subnet2 = aws.ec2.Subnet(
    "database_subnet2",
    cidr_block="172.31.16.0/20",
    vpc_id=vpc.id,
    availability_zone="eu-central-1b",
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

subnet3 = aws.ec2.Subnet(
    "database_subnet3",
    cidr_block="172.31.32.0/20",
    vpc_id=vpc.id,
    availability_zone="eu-central-1c",
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Create a new security group that allows TCP traffic on port 5432
secgrp_postgres = aws.ec2.SecurityGroup(
    "postgres_secgrp",
    vpc_id=vpc.id,
    ingress=[
        # Ingress rule to allow all tcp inbound traffic on port 5432
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp", from_port=5432, to_port=5432, cidr_blocks=["0.0.0.0/0"]
        ),
    ],
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Create a new RDS subnet group
subnet_group = aws.rds.SubnetGroup(
    "database_subnetgroup",
    subnet_ids=[subnet1.id, subnet2.id, subnet3.id],
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

ig = aws.ec2.InternetGateway(
    "my_ig",
    vpc_id=vpc.id,
    tags={
        "Name": "my_ig",
    },
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Create routing table
route_table = aws.ec2.RouteTable(
    "route_table",
    vpc_id=vpc.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Create a route that points all traffic (0.0.0.0/0) to the Internet Gateway
internet_route = aws.ec2.Route(
    "internet_access",
    route_table_id=route_table.id,
    destination_cidr_block="0.0.0.0/0",
    gateway_id=ig.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


# aws.ec2.VpcGatewayAttachment("my_vpc_gw", vpc_id=vpc.id, internet_gateway_id=ig.id)
route_table_association1 = aws.ec2.RouteTableAssociation(
    "route_table_association1",
    subnet_id=subnet1.id,
    route_table_id=route_table.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)
rroute_table_association2 = aws.ec2.RouteTableAssociation(
    "route_table_association2",
    subnet_id=subnet2.id,
    route_table_id=route_table.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)
oute_table_association3 = aws.ec2.RouteTableAssociation(
    "route_table_association3",
    subnet_id=subnet3.id,
    route_table_id=route_table.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Create a new Postgres RDS instance
instance = aws.rds.Instance(
    "user-db-pulumi",
    engine="postgres",
    instance_class="db.t3.micro",
    allocated_storage=10,
    db_subnet_group_name=subnet_group.name,
    vpc_security_group_ids=[secgrp_postgres.id],
    username="postgres",
    password=config.require_secret("dbPassword"),
    db_name="dashboard",
    publicly_accessible=True,
    skip_final_snapshot=True,
    # Use the provider with the assumed role
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


# Outputs
pulumi.export("postgres_endpoint", instance.address)
