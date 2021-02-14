import os
import platform
import subprocess
import sys
import logging
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

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
                # Ask CMake to place the resulting library in the directory
                # containing the extension
                '-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), ext_dir),
                # Other intermediate static libraries are placed in a
                # temporary build directory instead
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


setup(name='openwsn',
      packages=['openwsn'],
      version=1.0,
      description='An instance of an OpenWSN mote',
      author='Timothy Claeys',
      author_email='timothy.claeys@gmail.com',
      ext_modules=[CMakeExtension(c_module_name)],
      cmdclass={'build_ext': CMakeBuild},
      zip_safe=False)
