#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.dynamics_worker.worker import main
if __name__ == '__main__':
    main()
