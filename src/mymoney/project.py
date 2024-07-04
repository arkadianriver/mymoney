
import os, sys, yaml


cwd = os.path.abspath(os.path.curdir)


class Project:


  def __init__(self, period):
    self.config_file = f'{cwd}/config.yml'
    self.config = self.read_config_file()
    self.period = period
    self.transactions = []
    self.input = f'{cwd}/input/{period}'
    self.output = f'{cwd}/output/{period}'
    self.reports = f'{cwd}/reports/{period}'
    self.in_active_project = self.in_active_project()


  def ciao(self, msg, rc=0):
    print(msg)
    sys.exit(rc)


  def in_active_project(self):
    if not os.path.exists(self.config_file):
      self.ciao('Run the app from inside a project folder\nand create a project config file there.')
    if not os.path.exists(self.input):
      os.makedirs(f'{self.input}')
    if not os.path.exists(self.output):
      os.makedirs(f'{self.output}')
    if not os.path.exists(self.reports):
      os.makedirs(f'{self.reports}')
    return True
    

  def read_config_file(self):
    with open(self.config_file, 'r', encoding='utf-8-sig') as f:
	    return yaml.safe_load(f)


