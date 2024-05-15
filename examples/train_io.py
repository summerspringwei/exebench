import json
from typing import Optional, Tuple

from datasets import load_dataset, load_from_disk
from exebench import Wrapper, diff_io, exebench_dict_to_dict, LLVMAssembler, cpp2ass


def main():
    # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset("/data/xiachunwei/Datasets/exebench", split='train_real_simple_io') # , use_auth_token=True)
    # 2) Iterate over dataset
    print("Load dataset")
    for row in dataset:
        for key, value in row.items():
            print(f"key: {key}, value: {value}")
        print("*"*20)
        c_deps = row['real_deps'] if row['real_deps'] is not None else ""
        # c_deps += row['synth_io_pairs']['dummy_funcs'][0] if row['synth_io_pairs'] is not None else ""
        # c_deps += f'\nextern {row["func_head_types"].replace("extern", "")};\n'
        # with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        #     temp_file.write(row["func_def"])
        # cmd = f"clang++ -emit-llvm -o {temp_file.name}.ll -c {temp_file.name}"
        # with open("test.c", "w") as f:
        #     f.write(row["func_def"])
        # cmd = f"clang++ -emit-llvm -o test.ll -c test.c"
        # stdout, stderr = _run_command(cmd)
        # print(stdout)
        # print(stderr)
        # # cmd = f"cat {temp_file.name}.ll"
        # cmd = f"cat test.ll"
        # stdout, stderr = _run_command(cmd)
        # print(stdout)

        synth_wrapper = Wrapper(c_deps=c_deps + '\n',
                                    func_c_signature=row['func_head_types'].replace('extern', ''),
                                    func_assembly=row['asm']['code'][0],
                                    cpp_wrapper=row['real_exe_wrapper'],
                                    assembler_backend=LLVMAssembler(), func_def=row["func_def"])
        observed_output = synth_wrapper(exebench_dict_to_dict(row['real_io_pairs']['input'][0]))  # Run synthetic example number 0
        print('Input', exebench_dict_to_dict(row['real_io_pairs']['input'][0]))
        print('Observed Output:', observed_output)
        print('Does this output coincide with the expected one?',
                'Yes' if diff_io(observed_output=observed_output,
                                expected_output=exebench_dict_to_dict(row['real_io_pairs']['output'][0])) else 'No')
        break


def replace_with_space(c_deps: str, target: str) -> str:
    if c_deps.find(target) >= 0:
        c_deps = c_deps.replace(target, "")
    return c_deps

def preprocessing_c_deps(c_deps: str) -> str:
    statements_list = [
        "# 1",
        "typedef int bool;",
        "void* shmat (int,int /*<<< orphan*/ ,int /*<<< orphan*/ , ;",
        "int /*<<< orphan*/  write (int /*<<< orphan*/ ,char*,int, ;",
        "int /*<<< orphan*/  STDOUT_FILENO ;",
        "int /*<<< orphan*/  F_GETFL ;",
        "int /*<<< orphan*/  F_SETFL ;",
        "int /*<<< orphan*/  O_NONBLOCK ;",
        "int O_NONBLOCK ;",
        "int /*<<< orphan*/  warnx (char*, ; ",
        "int /*<<< orphan*/  tcsetattr (int /*<<< orphan*/ ,int /*<<< orphan*/ ,struct termios*, ;",
        "int /*<<< orphan*/  ioctl (int,int /*<<< orphan*/ ,int /*<<< orphan*/ , ;",
        "int open (char*,int, ;",
        "struct sockaddr_storage {int dummy; } ;",
        "struct sockaddr {int dummy; } ;",
        "int accept (int,struct sockaddr*,int*, ;",
        "int /*<<< orphan*/  bind (int,struct sockaddr*,int, ;",
        "void* memalign (int,size_t, ;",
        "struct sockaddr_in {int dummy; } ;",
        "struct sockaddr_in {TYPE_1__ sin_addr; int /*<<< orphan*/  sin_port; int /*<<< orphan*/  sin_family; } ;",
        "unsigned int recvfrom (int,char*,unsigned int,int /*<<< orphan*/ ,struct sockaddr*,int /*<<< orphan*/ *) ; "
        "int access (char*,int /*<<< orphan*/ ) ;",
        "int /*<<< orphan*/  openlog (char*,int /*<<< orphan*/ ,int /*<<< orphan*/ ) ;",
        "scalar_t__ tcgetattr (int,struct termios*) ;",
        "int read (int,char*,int) ;",
        "int recv (int,char*,int,int /*<<< orphan*/ ) ;",
        "int /*<<< orphan*/  epoll_ctl (int,int /*<<< orphan*/ ,int,int /*<<< orphan*/ ) ;",
        "int setsockopt (int,int /*<<< orphan*/ ,int,int*,int) ;",
        "int /*<<< orphan*/  swapon (char*,int) ;",
        "int /*<<< orphan*/  swapoff (char*) ;",
        "long syscall (int /*<<< orphan*/ ,unsigned int,unsigned long,struct kexec_segment*,unsigned long) ;",
        "int /*<<< orphan*/  htons (int) ;",
        "void* shmat (int,int /*<<< orphan*/ ,int /*<<< orphan*/ ) ;",
        "int /*<<< orphan*/  write (int /*<<< orphan*/ ,char*,int) ;",
        "int /*<<< orphan*/  warnx (char*) ;",
        "int /*<<< orphan*/  tcsetattr (int /*<<< orphan*/ ,int /*<<< orphan*/ ,struct termios*) ;",
        "int /*<<< orphan*/  tcsetattr (int /*<<< orphan*/ ,int /*<<< orphan*/ ,struct termios*) ;",
        "int /*<<< orphan*/  accept (int,struct sockaddr*,int*) ;",
        "int /*<<< orphan*/  bind (int,struct sockaddr*,int) ;",
        "int open (char*,int /*<<< orphan*/ ) ;",
        "long syscall (int /*<<< orphan*/ ,int /*<<< orphan*/ ,char const*,int /*<<< orphan*/ ,char const*,int const) ;",
        "int /*<<< orphan*/  write (int,char*,int) ;",
        "int access (char*,int /*<<< orphan*/ ) ;",
        "void* shmat (int,int /*<<< orphan*/ ,int /*<<< orphan*/ ) ;",
    ]
    for statement in statements_list:
        c_deps = replace_with_space(c_deps, statement)


    return c_deps


def main2():
     # 1) Load dataset split. In this case, synthetic test split
    dataset = load_dataset("/data/xiachunwei/Datasets/exebench", split='train_real_simple_io') # , use_auth_token=True)
    # 2) Iterate over dataset
    print("Load dataset")
    count = 0
    for row in dataset:
        for key, value in row.items():
            print(f"key: {key}, value: {value}")
        print("*"*20)
        count += 1
        c_deps = ""
        c_deps += row['real_deps'] +"\n" if row['real_deps'] is not None else ""
        # c_deps += row['synth_deps'] +"\n" if row['synth_deps'] is not None else ""
        # c_deps += row['synth_io_pairs']['dummy_funcs'][0] if row['synth_io_pairs'] is not None else ""
        # c_deps += f'\nextern {row["func_head_types"].replace("extern", "")};\n'
        # c_deps = preprocessing_c_deps(c_deps)
        c_deps += "#define bool char\n"
        
        # for key, value in row.items():
        #     print(f"key: {key}, value: {value}")
        # print("*"*20)
        print("c_deps:", c_deps)
        print("func_def:", row["func_def"])
        ass, success = cpp2ass(c_deps + row["func_def"])
        print("*"*20)
        if count>=1:
            break
    print(count)


from typing import Dict

def compile_assembly(row)->Dict:
    c_deps = ""
    # c_deps += row['real_deps'] +"\n" if row['real_deps'] is not None else ""
    if isinstance(c_deps, list):
        for deps in c_deps:
            c_deps += deps if deps is not None else ""
    
    # c_deps += row['synth_deps'] +"\n" if row['synth_deps'] is not None else " "
    c_deps += "#define bool char\n"
    try:
        success, _, ass = cpp2ass(c_deps + row["func_def"])
        if success:
            row["asm"]['target'].append('real_llvm_X86_O2')
            row["asm"]['code'].append(ass)
    except:
        print(f"Error for {row['path']}")
    
    return row


def get_all_assembly(path_to_dataset, split_name: str = "train_real_simple_io"):
    dataset = load_dataset(path_to_dataset, split=split_name) # , use_auth_token=True)
    # for row in dataset.select((0, 100)):
    #     print(row)
    dataset_with_assembly = dataset.map(compile_assembly, num_proc=40)
    # dataset_with_assembly = dataset.select((0, 100)).map(compile_assembly, batched=True, batch_size=20)
    dataset_with_assembly.save_to_disk("/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch")
    
    for row in dataset_with_assembly:
        print(row["asm"]['code'][-1])
        break


def convert_to_instruction_format(path_to_dataset, path_to_json):
    dataset = load_from_disk(path_to_dataset)
    programs_list = []
    for row in dataset:
        if row["asm"]['target'][-1] == "real_llvm_X86_O2":
            programs_list.append({
                "file": row['path'],
                "output": row["asm"]['code'][-1], 
                "input": row["asm"]['code'][-1],
                "instruction": "decompile the x86 assembly to llvm ir"
            })
    json.dump(programs_list, open(path_to_json, 'w'), indent=4, sort_keys=True)


if __name__ == '__main__':
    # main()
    # main2()
    # get_all_assembly("/data/xiachunwei/Datasets/exebench")
    convert_to_instruction_format("/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch", 
                         "/data/xiachunwei/Datasets/exebench/train_real_simple_io-llvm-assembly-batch.json")
