import sys
import logging
sys.path.insert(0, '/home/ubuntu/ssta/flaskapp')

from flaskapp.app import app as application

logging.basicConfig(stream=sys.stderr)
