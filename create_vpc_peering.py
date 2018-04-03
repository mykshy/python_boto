import boto3
import sys


REGION_NAME = 'ap-southeast-1'

client  = boto3.client('ec2', region_name=REGION_NAME)
ec2     = boto3.resource('ec2', region_name=REGION_NAME)


def get_main_route_table(vpc_id):
    rs = client.describe_route_tables(
        Filters=[
            {
                'Name': 'association.main',
                'Values': ['true']
            },
            {
                'Name': 'vpc-id',
                'Values': [vpc_id]
            }
        ]
    )

    return rs['RouteTables'][0]['RouteTableId']


def get_vpc_cidr(vpc_id):
    vpc = ec2.Vpc(vpc_id)
    return vpc.cidr_block


def create_public_subnet(vpc_id, subnet_cidr, subnet_availability_zone):
    rs = client.create_internet_gateway(DryRun=False)
    igw_id = rs['InternetGateway']['InternetGatewayId']

    client.attach_internet_gateway(
        InternetGatewayId=igw_id,
        VpcId=vpc_id,
        DryRun=False,
    )

    rs = client.create_subnet(
        AvailabilityZone=subnet_availability_zone,
        CidrBlock=subnet_cidr,
        VpcId=vpc_id,
        DryRun=False
    )

    subnet_id = rs['Subnet']['SubnetId']

    main_rtb_id = get_main_route_table(vpc_id)

    client.associate_route_table(
        RouteTableId=main_rtb_id,
        SubnetId=subnet_id,
        DryRun=False
    )

    client.create_route(
        RouteTableId=main_rtb_id,
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=igw_id,
        DryRun=False,
    )

    print '[OK] subnet [%s] as public subnet' % subnet_id


# create new vpc with one public subnet
def create_vpc_peering(vpc_cidr, subnet_cidr, subnet_availability_zone, target_vpc_id):
    rs = client.create_vpc(
        CidrBlock=vpc_cidr,
        AmazonProvidedIpv6CidrBlock=False,
        InstanceTenancy='default',
        DryRun=False,
    )

    vpc_id = rs['Vpc']['VpcId']
    print '[OK] vpc [%s] created' % vpc_id

    create_public_subnet(
        vpc_id=vpc_id,
        subnet_cidr=subnet_cidr,
        subnet_availability_zone=subnet_availability_zone
    )

    rs = client.create_vpc_peering_connection(
        PeerVpcId=target_vpc_id,
        VpcId=vpc_id,
        DryRun=False
    )

    pcx_id = rs['VpcPeeringConnection']['VpcPeeringConnectionId']
    client.accept_vpc_peering_connection(
        VpcPeeringConnectionId=pcx_id,
        DryRun=False
    )

    main_rtb_id = get_main_route_table(vpc_id=vpc_id)
    target_vpc_cidr = get_vpc_cidr(target_vpc_id)

    client.create_route(
        RouteTableId=main_rtb_id,
        DestinationCidrBlock=target_vpc_cidr,
        VpcPeeringConnectionId=pcx_id,
        DryRun=False,
    )

    target_vpc_main_rtb = get_main_route_table(target_vpc_id)

    client.create_route(
        RouteTableId=target_vpc_main_rtb,
        DestinationCidrBlock=vpc_cidr,
        VpcPeeringConnectionId=pcx_id,
        DryRun=False,
    )

    return vpc_id


if __name__ == '__main__':
    params = sys.argv[1:]
    if len(params) < 4:
        print ('Missing parameters.\nUse \'python create_vpc_peering.py <vpc_cidr> <subnet_cidr> <subnet_zone> <target_vpc_id>\'')
        exit(1)

    vpc_id = create_vpc_peering(
        vpc_cidr=params[0],
        subnet_cirdr=params[1],
        subnet_availability_zone=params[2],
        target_vpc_id=params[3]
    )

    print ('Peering [{}] - [{}] success'.format(vpc_id, params[3]))
