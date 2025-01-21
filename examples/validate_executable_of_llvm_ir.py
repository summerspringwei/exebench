import json
from typing import Optional, Tuple, Dict
import os
import datasets
from datasets import load_from_disk
from exebench import (Wrapper, LLVMAssembler, diff_io, exebench_dict_to_dict,
                      ll2ass)
import logging

import re

def extract_function_name(declaration):
    """
    Extracts the function name from a C++ or C function declaration.

    Args:
    declaration (str): A string containing the function declaration.

    Returns:
    str: The name of the function, or None if no function name is found.
    """
    # Regular expression pattern to match C++ and C function declarations
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(const)?\s*(;)?\s*$'
    
    # Search for the pattern in the declaration
    match = re.search(pattern, declaration)
    
    if match:
        return match.group(1)
    else:
        return None

def eval_assembly(row: Dict, assembly: str) -> bool:
    success = True
    synth_wrapper = None
    try:
        c_deps=(row['synth_deps'] + '\n' +
                    row['synth_io_pairs']['dummy_funcs'][0] + '\n').replace(
                        'typedef int bool;', '')
        synth_wrapper = Wrapper(
            c_deps=c_deps + '\n',
            func_c_signature=row['func_head_types'].replace('extern', ''),
            func_assembly=assembly,
            cpp_wrapper=row['synth_exe_wrapper'],
            # assembler_backend=LLVMAssembler()
            )
        count, total = 0, len(row['synth_io_pairs']['input'])
        for i, o in zip(row['synth_io_pairs']['input'],
                        row['synth_io_pairs']['output']):
            observed_output = synth_wrapper(
                exebench_dict_to_dict(i))  # Run synthetic
            if observed_output is None:
                logging.error('Error: The code could not be compiled')
                success = False
                return success
            # print(observed_output, exebench_dict_to_dict(o))
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


def strip_bss_in_assembly(asm: str)->str:
    pattern = ".cfi_endproc"
    idx = asm.find(pattern)
    return asm[:idx+len(pattern)]

import tempfile
import subprocess

def main():
    i=0
    # saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir_assembly_O2"
    saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir"
    b = load_from_disk(saved_path).select(range(0, 20))
    print(len(b))
    for row in b:
        func_name = extract_function_name(row['func_head'])
        if func_name is None:
            logging.error(f"Can not extract function name from {row['func_head']}")
            continue
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp_file:
            temp_file.write(row["llvm_ir"]["code"][-1])
            temp_file.flush()
            result = subprocess.run(["llvm-extract", "-func", func_name, "-S", temp_file.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                print("Error: ", result.stderr.decode())
            asm = ll2ass(result.stdout.decode())
            if asm is None:
                continue
            # asm = strip_bss_in_assembly(asm)
            success = eval_assembly(row, asm)
            print("success: ", success)


def test():
    for i in range(8):
        saved_path = f"/data/xiachunwei/Datasets/filtered_exebench/train_synth_rich_io_filtered_llvm_ir/train_synth_rich_io_filtered_{i}_llvm_ir_assembly_O2"
        b = load_from_disk(saved_path)
        print(len(b))

if __name__ == '__main__':
    main()
    # test()
