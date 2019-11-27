#!/usr/bin/python
################################################################################
# filetrigger - watch a directory for a file appearance, then trigger indicated action
#
# Author: L King
#
# REVISION HISTORY:
#   02/15/12    L King      create
#   03/08/12    L King      add optional exitevent    
################################################################################
"""
filetrigger - watch a directory for a file appearance, then trigger indicated action
============================================================================================

Provides filetrigger class, which can be used to process a file when it discovers that file is placed in a specified directory.
    
"""

# standard libraries
from optparse import OptionParser
import time
import glob
import tempfile
import shutil
import os
import os.path
import subprocess
import sys

# pypi libraries

# home grown libraries

class invalidParameter(Exception): pass

################################################################################
class filetrigger():
################################################################################
    """
    When :meth:`run` executed, periodically checks dir for a file which does not start 
    with 'tmp.'. 
    
    When a file arrives in triggerdir, the file is moved to an 'active' temporary directory, 
    :meth:`cleanup` is invoked, the previous file is deleted,  then :meth:`processfile`
    is invoked.  
    
    This class must be inherited.  In the inherited class, :meth:`processfile` and 
    :meth:`cleanup` must be overridden.
    
    :param triggerdir: directory to check for arrival of file
    :param period: period in seconds between checking triggerdir
    :param exitevent: caller will set this event when exit is desired (optional)
    """
    
    ################################################################################
    def __init__(self,triggerdir,period,exitevent=None):
    ################################################################################
    
        self.triggerdir = triggerdir
        self.period = period
        self.exitevent = exitevent
        
    ################################################################################
    def processfile(self,activefilepath):
    ################################################################################
        """
        This method must be overridden by the inheriting class.  This method processes
        the activefilepath until :meth:`cleanup` is invoked.
        
        This method must not block the caller.
        
        :param activefilepath: path of file which has been "activated" by being placed in triggerdir
        """
        pass
        
    ################################################################################
    def cleanup(self,lastfilepath):
    ################################################################################
        """
        This method must be overridden by the inheriting class.  Expectation is that
        this class will stop the action being done by :meth:`processfile`. 
        
        This method must block the caller until any cleanup is completed.
        
        :param lastfilepath: path of file which has been "activated" by being placed in triggerdir
        """
        pass
        
    ################################################################################
    def run(self):
    ################################################################################
        """
        Invoke this method to start execution
        """
        
        # create tempdir to hold active file
        activedir = tempfile.mkdtemp(prefix='filetrigger')
        
        self.prevfile = None
        try:
            while True:
                if self.exitevent and self.exitevent.is_set(): break
                
                time.sleep(self.period)
                files = glob.glob('{0}/*'.format(self.triggerdir))
                files = [f for f in files if os.path.basename(f)[0:4] != 'tmp.'] # don't care about tmp.*
                if len(files) > 1: raise invalidParameter(
                    'multiple files found in {0}: {1}'.format(self.triggerdir, files))
                
                # did we find a new file?
                if len(files) == 1:
                    thisfile = files[0]
                    
                    filebase = os.path.basename(thisfile)
                    src = os.path.join(self.triggerdir,filebase)
                    activefile = os.path.join(activedir,filebase)
                    shutil.move(src,activefile)
                    
                    # first time through, self.prevfile will be empty
                    # otherwise, terminate old process and delete the old file
                    if self.prevfile is not None:
                        self.cleanup(self.prevfile)
                        os.remove(self.prevfile)
                        
                    # start process for this file - must not be blocking
                    self.processfile(activefile)
                    
                    # remember what is going on
                    self.prevfile = activefile
                    
        except KeyboardInterrupt:
            pass
        finally:
            if self.prevfile is not None:
                self.cleanup(self.prevfile)
            shutil.rmtree(activedir)
                
################################################################################
class _testfiletrigger(filetrigger):
################################################################################
    """
    for unit test only
    """

    ################################################################################
    def __init__(self,triggerdir):
    ################################################################################
    
        self.triggerdir = triggerdir
        filetrigger.__init__(self,self.triggerdir,5) # 5 second check period
        
    ################################################################################
    def processfile(self,activefilepath):
    ################################################################################
        """
        This method must not block the caller.
        
        :param activefilepath: path of file which has been "activated" by being placed in triggerdir
        """
        
        # this crude test just runs the file which was put into the directory, with the filename as a parameter
        # start subprocess, non-blocking, return the process id
        self.activeprocess = subprocess.Popen(['python', activefilepath, activefilepath],stdout=sys.stdout,stderr=sys.stderr)
        
    ################################################################################
    def cleanup(self, lastfilepath):
    ################################################################################
        """
        This method must block the caller until any cleanup is completed.
        
        :param lastfilepath: path of file which has been "activated" by being placed in triggerdir
        """
        
        self.activeprocess.terminate()
        
################################################################################
def main():
################################################################################
    """
    Use main to model your application to call :meth:`run`, or to test this module
    """

    usage  = "  ./filetrigger.py directory  \n"
    usage += "     where: directory is directory to look for file appearance"

    parser = OptionParser(usage=usage)
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        raise invalidParameter("requires directory parameter")
    
    directory = args.pop(0)
    directory = os.path.abspath(directory)
    
    # instantiate the test class, and run
    tc = _testfiletrigger(directory)
    tc.run()
    
# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()
