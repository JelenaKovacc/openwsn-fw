import json
import os
import platform
import re
import subprocess
import sys
import logging
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install

# Filename for the C extension module library
c_module_name = '_openmote'

# Command line flags forwarded to CMake (for debug purpose)
cmake_cmd_args = []
for f in sys.argv:
    if f.startswith('-D'):
        cmake_cmd_args.append(f)

for f in cmake_cmd_args:
    sys.argv.remove(f)


def _get_env_variable(name, default='OFF'):
    if name not in os.environ.keys():
        return default
    return os.environ[name]


class CMakeExtension(Extension):
    def __init__(self, name, cmake_lists_dir='.', sources=None, **kwa):
        if sources is None:
            _sources = []
        else:
            _sources = sources
        Extension.__init__(self, name, sources=_sources, **kwa)
        self.cmake_lists_dir = os.path.abspath(cmake_lists_dir)


class PreInstallCommand(install):
    print("running pre-install scripts")

    def run(self):
        base_path = os.path.abspath('.')

        with open(os.path.join(base_path, 'openwsn', 'opendefs.py'), 'w') as f:
            f.write('component_codes = ')
            f.write(json.dumps(self.extract_component_codes(base_path)))
            f.write('\n')
            f.write('log_descriptions = ')
            f.write(json.dumps(self.extract_log_descriptions(base_path)))

        with open(os.path.join(base_path, 'openwsn', 'sixtop.py'), 'w') as f:
            f.write('sixtop_rcs = ')
            f.write(json.dumps(self.extract_6top_rcs(base_path)))
            f.write('\n')
            f.write('sixtop_states = ')
            f.write(json.dumps(self.extract_6top_states(base_path)))

        install.run(self)

    @staticmethod
    def extract_component_codes(base_path):
        codes_found = {}

        for line in open(os.path.join(base_path, 'inc', 'opendefs.h'), 'r'):
            m = re.search(' *COMPONENT_([^ .]*) *= *(.*), *', line)
            if m:
                name = m.group(1)
                try:
                    code = int(m.group(2), 16)
                except ValueError:
                    logging.error("component '{}' - {} is not a hex number".format(name, m.group(2)))
                else:
                    logging.debug("extracted component '{}' with code {}".format(name, code))
                    codes_found[code] = name

        return codes_found

    @staticmethod
    def extract_log_descriptions(base_path):

        codes_found = {}
        for line in open(os.path.join(base_path, 'inc', 'opendefs.h'), 'r'):
            m = re.search(' *ERR_.* *= *([xXA-Fa-f0-9]*), *// *(.*)', line)
            if m:
                desc = m.group(2).strip()
                try:
                    code = int(m.group(1), 16)
                except ValueError:
                    logging.error("log description '{}' - {} is not a hex number".format(desc, m.group(2)))
                else:
                    logging.debug("extracted log description '{}' with code {}".format(desc, code))
                    codes_found[code] = desc

        return codes_found

    @staticmethod
    def extract_6top_rcs(base_path):
        # find sixtop return codes in sixtop.h

        codes_found = {}
        for line in open(os.path.join(base_path, 'openstack', '02b-MAChigh', 'sixtop.h'), 'r'):
            m = re.search(' *#define *IANA_6TOP_RC_([^ .]*) *([xXA-Za-z0-9]+) *// *([^ .]*).*', line)
            if m:
                name = m.group(3)
                try:
                    code = int(m.group(2), 16)
                except ValueError:
                    logging.error("return code '{}': {} is not a hex number".format(name, m.group(2)))
                else:
                    logging.debug("extracted 6top RC '{}' with code {}".format(name, code))
                    codes_found[code] = name

        return codes_found

    @staticmethod
    def extract_6top_states(base_path):
        # find sixtop state codes in sixtop.h

        codes_found = {}
        for line in open(os.path.join(base_path, 'openstack', '02b-MAChigh', 'sixtop.h'), 'r'):
            m = re.search(' *SIX_STATE_([^ .]*) *= *([^ .]*), *', line)
            if m:
                name = m.group(1)
                try:
                    code = int(m.group(2), 16)
                except ValueError:
                    logging.error("state '{}' - {} is not a hex number".format(name, m.group(2)))
                else:
                    logging.debug("extracted 6top state '{}' with code {}".format(name, code))
                    codes_found[code] = name

        return codes_found


class CMakeBuild(build_ext):
    def build_extensions(self):
        # Ensure that CMake is present and working
        try:
            out = subprocess.check_output(['cmake', '--version'])
            logging.info(out)
        except OSError:
            raise RuntimeError('Cannot find CMake executable')

        for ext in self.extensions:

            ext_dir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
            cfg = 'Debug'

            cmake_args = [
                '-DCMAKE_BUILD_TYPE=%s' % cfg,
                # Ask CMake to place the resulting library in the directory containing the extension
                '-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), ext_dir),
                # Other intermediate static libraries are placed in a temporary build directory instead
                '-DCMAKE_ARCHIVE_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), self.build_temp),
            ]

            # We can handle some platform-specific settings at our discretion
            if platform.system() == 'Windows':
                plat = ('x64' if platform.architecture()[0] == '64bit' else 'Win32')
                cmake_args += [
                    # These options are likely to be needed under Windows
                    '-DCMAKE_WINDOWS_EXPORT_ALL_SYMBOLS=TRUE',
                    '-DCMAKE_RUNTIME_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), ext_dir),
                ]
                # Assuming that Visual Studio and MinGW are supported compilers
                if self.compiler.compiler_type == 'msvc':
                    cmake_args += [
                        '-DCMAKE_GENERATOR_PLATFORM=%s' % plat,
                    ]
                else:
                    cmake_args += [
                        '-G', 'MinGW Makefiles',
                    ]

            cmake_args += cmake_cmd_args

            if not os.path.exists(self.build_temp):
                os.makedirs(self.build_temp)

            # Config
            subprocess.check_call(
                ['cmake', ext.cmake_lists_dir, '-DBOARD:STRING=python', '-DPROJECT:STRING=oos_openwsn'] + cmake_args,
                cwd=self.build_temp)

            # Build
            subprocess.check_call(['cmake', '--build', '.', '--config', cfg], cwd=self.build_temp)
            pass


setup(name='openwsn',
      packages=['openwsn'],
      version=1.0,
      description='An instance of an OpenWSN mote',
      author='Timothy Claeys',
      author_email='timothy.claeys@gmail.com',
      ext_modules=[CMakeExtension(c_module_name)],
      cmdclass={
          'build_ext': CMakeBuild,
          'install': PreInstallCommand
      },
      zip_safe=False)
