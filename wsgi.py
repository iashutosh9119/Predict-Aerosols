import sys
import logging
sys.path.insert(0, '/home/ubuntu/SSTA/flaskapp')

from flaskapp.app import app as application

logging.basicConfig(stream=sys.stderr)
