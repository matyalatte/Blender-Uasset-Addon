import time, traceback

class Logger:
    LOG_FOLDER='log'
    def __init__(self):
        #os.makedirs(Logger.LOG_FOLDER, exist_ok=True)
        #self.file_name = time.strftime('%Y%m%d-%H%M%S'+'.txt')
        #file_path=os.path.join(Logger.LOG_FOLDER, self.file_name)
        #self.f=open(file_path, 'w')
        self.warnings = []

    def set_verbose(self, verbose):
        self.verbose=verbose

    def close(self):
        if len(self.warnings)>0:
            [self.log('Warning: ' + w, ignore_verbose=True) for w in self.warnings]
            self.log('You got {} warning{}. Check the console outputs.'.format(len(self.warnings), 's'*(len(self.warnings)>1)))
        #self.f.close()

    def log(self, string, ignore_verbose=False):
        #self.f.write('{}\n'.format(string))
        if self.verbose or ignore_verbose:
            print(string)

    def error(self):
        self.log(traceback.format_exc()[:-1])
        self.close()
        #file_path=os.path.join(Logger.LOG_FOLDER, self.file_name)
        #self.file_name = 'error-'+self.file_name
        #err_file_path=os.path.join(Logger.LOG_FOLDER, self.file_name)
        #os.rename(file_path, err_file_path)

    def warn(self, warning):
        #self.log('Warning: ' + warning, ignore_verbose=True)
        self.warnings.append(warning)

class Timer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.start=time.time()

    def now(self):
        return time.time()-self.start

logger = Logger()
logger.set_verbose(False)