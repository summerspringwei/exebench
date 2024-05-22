import math
import json
from pathlib import Path
import subprocess
from typing import Optional, Tuple, Dict
import tempfile
import contextlib
import os
import shutil
import glob
import re
from ast import literal_eval
import logging
import re

# Set up logging
logging.basicConfig(
    format=
    '%(asctime)s - %(levelname)s - %(filename)s - Line: %(lineno)d - %(message)s',
    level=logging.DEBUG)

__all__ = [
    'diff_io', 'Wrapper', 'exebench_dict_to_dict', 'LLVMAssembler', 'cpp2ass',
    'll2ass'
]

__version__ = 0.1

# UTILS (in a self-contained file to ease deployment)

_DEFAULT_CMD_TIMEOUT = 15
_ROOT_PATH_FOR_JSON_HPP = os.path.dirname(__file__)
_SYNTH_LIBS_PATH = os.path.dirname(__file__)


def _run_command(
        command: str,
        stdin: Optional[str] = None,
        timeout: Optional[int] = _DEFAULT_CMD_TIMEOUT) -> Tuple[str, str]:
    output = subprocess.run(command.split(),
                            capture_output=True,
                            text=True,
                            input=stdin,
                            timeout=timeout)
    stdout = output.stdout.decode('utf-8') if isinstance(
        output.stdout, bytes) else output.stdout
    stderr = output.stderr.decode('utf-8') if isinstance(
        output.stderr, bytes) else output.stderr
    return output.returncode, stdout, stderr


def _get_host_process_id():
    process_id = 'exebench_' + os.uname()[1] + '_' + str(os.getpid())
    return process_id


def _cleanup(path_pattern):
    for path in glob.glob(path_pattern):
        try:
            shutil.rmtree(path)
        except:
            pass


@contextlib.contextmanager
def _get_tmp_path(content: Optional[str] = None,
                  suffix: Optional[str] = None,
                  delete=False) -> str:
    prefix = _get_host_process_id()
    try:
        with tempfile.NamedTemporaryFile(prefix=prefix,
                                         suffix=suffix,
                                         delete=delete,
                                         mode='w+') as ntf:
            if content:
                ntf.write(content)
                ntf.flush()
            yield ntf.name
    except OSError:
        _cleanup(os.path.join(tempfile.gettempdir(), prefix, '*'))
        with tempfile.NamedTemporaryFile(prefix=prefix,
                                         suffix=suffix,
                                         delete=delete,
                                         mode='w+') as ntf:
            if content:
                ntf.write(content)
                ntf.flush()
            yield ntf.name


class _Assembler:
    def __call__(self, c_deps, func_c_signature, func_assembly,
                 cpp_wrapper) -> Path:
        raise NotImplemented


class _DefaultAssembler(_Assembler):
    def __call__(self, c_deps, func_c_signature, func_assembly,
                 cpp_wrapper) -> Path:
        with _get_tmp_path(content=None, suffix='.x',
                           delete=False) as executable_path:
            c_deps += f'\nextern {func_c_signature};\n'
            with _get_tmp_path(content=c_deps, suffix='.c') as c_deps_path:
                cpp_wrapper = re.sub(r'extern\s\"C\"\s\{\s.*\s\}',
                                     'extern "C" \n{\n#include "' +
                                     c_deps_path + '"\n}\n',
                                     cpp_wrapper)  # replace tmp path
                with _get_tmp_path(content=cpp_wrapper, suffix='.cpp') as cpp_path, \
                        _get_tmp_path(content=func_assembly, suffix='.s') as s_path:

                    cmd = f'g++ -fpermissive -O0 -o {executable_path} {cpp_path} {s_path} -I {_ROOT_PATH_FOR_JSON_HPP} -I{_SYNTH_LIBS_PATH}'

                    returncode, stdout, stderr = _run_command(cmd)
                    if returncode != 0:
                        logging.error(f"Executing {cmd} failed with {stderr}")
                        return None

        return Path(executable_path)


def _compile_exe_path(c_deps, func_c_signature, func_assembly, cpp_wrapper,
                      assembler_backend):
    return assembler_backend(c_deps, func_c_signature, func_assembly,
                             cpp_wrapper)


# API


def contrain_error(content: str) -> bool:
    pattern = re.compile(r'error|Error:|ERROR|Error')
    return bool(pattern.search(content))


def cpp2ass(cpp_code: str, opt_level="-O2") -> Tuple[bool, str, str]:
    """Converts C++ code to assembly code and llvm using clang and llc.
    
    """
    success, ll_code, s_code = True, None, None
    try:
        with _get_tmp_path(content=cpp_code, suffix='.c') as cpp_path:
            with _get_tmp_path(content=None, suffix='.s') as s_path:
                cmd = f"clang {opt_level} -emit-llvm -S -o {str(cpp_path)}.ll -c {cpp_path}"
                returncode, stdout, stderr = _run_command(cmd)
                if returncode != 0 or contrain_error(stderr):
                    success = False
                    logging.error(f"Executing {cmd} got {stderr}")
                cmd = f"llc -o {s_path} {str(cpp_path)}.ll"
                returncode, stdout, stderr = _run_command(cmd)
                if returncode != 0 or contrain_error(stderr):
                    success = False
                    logging.error(f"Executing {cmd} got {stderr}")
                with open(s_path, 'r') as f:
                    s_code = f.read()
                with open(f"{str(cpp_path)}.ll", 'r') as f:
                    ll_code = f.read()
                return success, ll_code, s_code
    except Exception as e:
        success, ll_code, s_code = False, None, None
        logging.error(f"Error: {e}")
    finally:
        return success, ll_code, s_code


def ll2ass(ll_code: str) -> str:
    with _get_tmp_path(content=ll_code, suffix='.ll') as ll_path:
        with _get_tmp_path(content=None, suffix='.s') as s_path:
            cmd = f"llc -o {s_path} {ll_path}"
            returncode, stdout, stderr = _run_command(cmd)
            if stderr.find("error") != -1:
                print(stderr)
            with open(s_path, 'r') as f:
                s_code = f.read()
            return s_code


class LLVMAssembler(_Assembler):
    def __call__(self, c_deps, func_c_signature, func_assembly,
                 cpp_wrapper) -> Path:
        with _get_tmp_path(content=None, suffix='.x',
                           delete=False) as executable_path:
            c_deps += f'\nextern {func_c_signature};\n'
            with _get_tmp_path(content=c_deps, suffix='.c') as c_deps_path:
                cpp_wrapper = re.sub(r'extern\s\"C\"\s\{\s.*\s\}',
                                     'extern "C" \n{\n#include "' +
                                     c_deps_path + '"\n}\n',
                                     cpp_wrapper)  # replace tmp path
                with _get_tmp_path(content=cpp_wrapper, suffix='.cpp') as cpp_path, \
                        _get_tmp_path(content=func_assembly, suffix='.s') as s_path:

                    cmd = f'clang++ -fpermissive -O0 -o {executable_path} {cpp_path} {s_path} -I {_ROOT_PATH_FOR_JSON_HPP} -I{_SYNTH_LIBS_PATH}'

                    returncode, stdout, stderr = _run_command(cmd)
                    if returncode != 0 or contrain_error(stderr):
                        logging.error(f"Executing {cmd} failed with {stderr}")
                        return None

        return Path(executable_path)


class Wrapper:
    def __init__(self,
                 c_deps,
                 func_c_signature,
                 func_assembly,
                 cpp_wrapper,
                 assembler_backend=_DefaultAssembler(),
                 func_def: str = None,
                 ll_code: str = None):
        self._compiled_exe_path = self._compile_exe_path(
            c_deps, func_c_signature, func_assembly, cpp_wrapper,
            assembler_backend, func_def, ll_code)

    @staticmethod
    def _compile_exe_path(c_deps,
                          func_c_signature,
                          func_assembly,
                          cpp_wrapper,
                          assembler_backend,
                          func_def: str = None,
                          ll_code: str = None):
        success = True
        if func_def is not None:
            success, _, func_assembly = cpp2ass(func_def)
        if ll_code is not None:
            func_assembly = ll2ass(ll_code)
        if (func_def is not None or ll_code is not None) and not success:
            return None
        return _compile_exe_path(c_deps, func_c_signature, func_assembly,
                                 cpp_wrapper, assembler_backend)

    def __call__(self, inp, return_stdout_and_stderr=False):
        executable = self._compiled_exe_path
        if executable is None:
            return None
        with _get_tmp_path(content=None,
                           suffix='.json') as input_tmp_json_path:
            output_file = ''.join(
                input_tmp_json_path.split(".")[:1]) + '-out.json'

            with open(input_tmp_json_path, 'w') as f:
                json.dump(inp, f)

            returncode, stdout, stderr = _run_command(
                f'{executable} {input_tmp_json_path} {output_file}')

            with open(output_file, 'r') as f:
                output = json.load(f)
            os.remove(output_file)

        if return_stdout_and_stderr:
            return output, stdout, stderr

        return output


def diff_io(observed_output, expected_output) -> bool:
    if type(observed_output) is not type(expected_output):
        return False
    if isinstance(observed_output, list):
        if len(observed_output) != len(expected_output):
            return False
        for e1, e2 in zip(observed_output, expected_output):
            ok = diff_io(e1, e2)
            if not ok:
                return False
    elif isinstance(observed_output, dict):
        for key in observed_output:
            if key not in expected_output:
                return False
            ok = diff_io(observed_output[key], expected_output[key])
            if not ok:
                return False
    elif isinstance(observed_output, float):
        ok = math.isclose(observed_output, expected_output)
        if not ok:
            return False
    else:
        ok = observed_output == expected_output
        if not ok:
            return False
    return True


def _fix_nested_dict(inp):  # hack

    if isinstance(inp, dict):
        for k in inp:
            inp[k] = _fix_nested_dict(inp[k])
    elif isinstance(inp, list):
        for idx, e in enumerate(inp):
            inp[idx] = _fix_nested_dict(e)
    else:
        return literal_eval(inp)
    return inp


def exebench_dict_to_dict(exebench_dict):
    keys = exebench_dict['var']
    values = exebench_dict['value']
    return _fix_nested_dict({k: v for k, v in zip(keys, values)})


def preprocessing_c_deps(row) -> str:
    c_deps = ""
    c_deps += row['real_deps'] + "\n" if row['real_deps'] is not None else ""
    replacements = ["typedef int bool;"]
    for r in replacements:
        if c_deps.find(r) != -1:
            c_deps = c_deps.replace(r, "").strip()

    if c_deps == "" and row['synth_deps'] is not None:
        c_deps += row['synth_deps'] + "\n"
    for r in replacements:
        if c_deps.find(r) != -1:
            c_deps = c_deps.replace(r, "").strip()
    return c_deps + "\n"


def eval_assembly(row: Dict, assembly: str) -> bool:
    success = True
    synth_wrapper = None
    try:
        c_deps = preprocessing_c_deps(row)
        synth_wrapper = Wrapper(
            c_deps=c_deps + '\n',
            func_c_signature=row['func_head_types'].replace('extern', ''),
            func_assembly=assembly,
            cpp_wrapper=row['real_exe_wrapper'],
            assembler_backend=LLVMAssembler())
        count, total = 0, len(row['real_io_pairs']['input'])
        for i, o in zip(row['real_io_pairs']['input'],
                        row['real_io_pairs']['output']):
            observed_output = synth_wrapper(
                exebench_dict_to_dict(i))  # Run synthetic
            if observed_output is None:
                logging.error('Error: The code could not be compiled')
                success = False
                return success
            count += 1 if diff_io(
                observed_output=observed_output,
                expected_output=exebench_dict_to_dict(o)) else 0
        success = (count == total)
        if not success:
            logging.info(
                f"Error for {row['path']} total cases {total}, success cases {count}"
            )
    except Exception as e:
        logging.error(f"Error for {row['path']}")
        logging.error(e)
        success = False
    finally:
        return success
