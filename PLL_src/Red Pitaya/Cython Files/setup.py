from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize

dir={'language_level':3,'boundscheck':False,'cdivision':True,'wraparound':False}


extensions= [
    Extension("runPLL",["runPLL.pyx"], compiler_directives=dir),
    Extension("Sweeper",["Sweeper.pyx"], compiler_directives=dir),
]
setup(
    ext_modules = cythonize(extensions),

)
