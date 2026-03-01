"""
Local numpy recipe override — pins numpy 1.26.4 for NDK r25b compatibility.

NumPy 2.x uses C++17 std::unordered_map in unique.cpp which NDK r25b's
libc++ doesn't support. NumPy 1.26.4 (last 1.x release) builds cleanly.
"""

from pythonforandroid.recipe import Recipe, MesonRecipe
from os.path import join
import shutil

NUMPY_NDK_MESSAGE = (
    "In order to build numpy, you must set minimum ndk api (minapi) to `24`.\n"
)


class NumpyRecipe(MesonRecipe):
    version = '1.26.4'
    url = 'https://github.com/numpy/numpy/releases/download/v{version}/numpy-{version}.tar.gz'
    hostpython_prerequisites = ["Cython>=3.0.6"]
    extra_build_args = ['-Csetup-args=-Dblas=none', '-Csetup-args=-Dlapack=none']
    need_stl_shared = True
    min_ndk_api_support = 24

    def get_recipe_meson_options(self, arch):
        options = super().get_recipe_meson_options(arch)
        options["binaries"]["python"] = self.ctx.python_recipe.python_exe
        options["binaries"]["python3"] = self.ctx.python_recipe.python_exe
        options["properties"]["longdouble_format"] = (
            "IEEE_DOUBLE_LE" if arch.arch in ["armeabi-v7a", "x86"]
            else "IEEE_QUAD_LE"
        )
        return options

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["_PYTHON_HOST_PLATFORM"] = arch.command_prefix
        env["NPY_DISABLE_SVML"] = "1"
        env["TARGET_PYTHON_EXE"] = join(
            Recipe.get_recipe("python3", self.ctx).get_build_dir(arch.arch),
            "android-build", "python"
        )
        return env

    def build_arch(self, arch):
        super().build_arch(arch)
        self.restore_hostpython_prerequisites(["cython"])

    def get_hostrecipe_env(self, arch=None):
        env = super().get_hostrecipe_env(arch=arch)
        env['RANLIB'] = shutil.which('ranlib')
        return env


recipe = NumpyRecipe()
