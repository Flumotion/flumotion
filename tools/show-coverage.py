import os
import sys

class Coverage:
    def __init__(self):
        self.files = []
        self.total_lines = 0
        self.total_covered = 0
        
    def add_file(self, file):
        self.files.append(file)

    def show_results(self):
        self.maxlen = max(map(lambda f: len(self._strip_filename(f)),
                              self.files))
        print 'Coverage report:'
        print '=' * (self.maxlen + 5)
        for file in self.files:
            self.show_one(file)
            
        percent = 100 * self.total_covered / float(self.total_lines)
        print '=' * (self.maxlen + 5)
        print 'Total: %d%% coverage' % percent

    def _strip_filename(self, filename):
        filename = os.path.basename(filename)
        if filename.endswith('.cover'):
            filename = filename[:-6]
        return filename
        
    def show_one(self, filename):
        f = open(filename)
        lines = f.readlines()

        lines = [line for line in lines
                         if (':' in line or line.startswith('>>>>>>')) and
                           not line.strip().startswith('#') and
                           not line.endswith(':\n')]

        uncovered_lines = [line for line in lines
                                   if line.startswith('>>>>>>')]
        if not lines:
            return
        
        no_lines = len(lines)
        no_covered = no_lines - len(uncovered_lines)
        self.total_lines += no_lines
        self.total_covered += no_covered

        if no_covered == 0:
            percent = 0
        else:
            percent = 100 * no_covered / float(no_lines)

        filename = self._strip_filename(filename)

        format = '%%-%ds %%3d%%%%' % self.maxlen
        print format % (filename, percent)
        
def main(args):
    c = Coverage()
    files = args[1:]
    files.sort()
    for file in files:
        if 'flumotion.test' in file:
            continue
        if '__init__' in file:
            continue
        c.add_file(file)

    c.show_results()
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
