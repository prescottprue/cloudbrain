__author__ = 'marion'

# add the shared settings file to namespace
import sys
import argparse
from os.path import dirname, abspath

sys.path.insert(0, dirname(dirname(abspath(__file__))))
import settings
from spacebrew.spacebrew import SpacebrewApp
import json


class SpacebrewClient(object):
    def __init__(self, name, server):
        # configure the spacebrew client
        self.brew = SpacebrewApp(name, server=server)
        self.paths = ['/muse/eeg',
                      '/muse/acc',
                      '/muse/elements/experimental/concentration',
                      '/muse/elements/experimental/mellow']

        for path in self.paths:
            spacebrew_name = path.split('/')[-1]
            self.brew.add_subscriber(spacebrew_name, "string")
            self.brew.subscribe(spacebrew_name, self.handle_value)

    def handle_value(self, string_value):
        # put your code here

        value = json.loads(string_value)
        print value

    def start(self):
        self.brew.start()


parser = argparse.ArgumentParser(
    description='Receive data from Spacebrew.')
parser.add_argument(
    '--name',
    help='Your name or ID without spaces or special characters',
    default='example')

if __name__ == "__main__":
    args = parser.parse_args()
    sb_client = SpacebrewClient('booth-%s' % args.name, settings.CLOUDBRAIN_ADDRESS)
    sb_client.start()
