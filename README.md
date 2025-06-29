# freqtrade
repo for custom freqtrade bot
this branch contains an example of a kafka producer consumer pair using msk
to run this example:
- create ssh key pair
- run terraform to create architecture
- replace names of msk-brokers in script
- connect to ec2 with ssh
- install docker on ec2
- copy consumer and producer directories to ec2
- build and run consumer and producer containers
