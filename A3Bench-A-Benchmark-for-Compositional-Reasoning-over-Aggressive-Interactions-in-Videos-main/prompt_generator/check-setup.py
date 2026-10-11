import sys
from pathlib import Path

def check_file(path, description):
    if path.exists():
        print(f"? {description}: {path.name}")
        return True
    else:
        print(f"? MISSING {description}: {path.name}")
        return False

def main():
    print("=" * 60)
    print("Checking prompt_generator setup...")
    print("=" * 60)


    current_dir = Path.cwd()
    print(f"\nCurrent directory: {current_dir}")


    print("\n[Core Files]")
    core_files = [
        (current_dir / "generator.py", "Question generator"),
        (current_dir / "templates.py", "Question templates"),
        (current_dir / "answer_bank.py", "Answer bank"),
        (current_dir / "cli.py", "CLI module"),
        (current_dir / "__init__.py", "Package init"),
    ]

    core_ok = all(check_file(path, desc) for path, desc in core_files)


    print("\n[Evaluation Module]")
    eval_dir = current_dir / "evaluation"
    if eval_dir.exists() and eval_dir.is_dir():
        print(f"? Evaluation directory exists")
        eval_files = [
            (eval_dir / "__init__.py", "Evaluation init"),
            (eval_dir / "evaluator.py", "Evaluator"),
            (eval_dir / "model_loader.py", "Model loader"),
            (eval_dir / "video_processor.py", "Video processor"),
            (eval_dir / "run_evaluation.py", "Run script"),
        ]
        eval_ok = all(check_file(path, desc) for path, desc in eval_files)
    else:
        print(f"? Evaluation directory not found")
        eval_ok = False


    print("\n[Documentation]")
    check_file(current_dir / "README.md", "README")
    check_file(current_dir / "requirements.txt", "Requirements")


    print("\n" + "=" * 60)
    if core_ok and eval_ok:
        print("? Setup is CORRECT!")
        print("\nYou can now run:")
        print("  python -m evaluation.run_evaluation ...")
        print("Or:")
        print("  python main.py ...")
        return 0
    else:
        print("? Setup is INCOMPLETE!")
        print("\nYou need to copy ALL files from prompt_generator:")
        print("  - Core files (generator.py, templates.py, etc.)")
        print("  - evaluation/ folder with all its contents")
        print("\nMake sure the directory structure looks like:")
        print("  project/")
        print("  +-- generator.py")
        print("  +-- templates.py")
        print("  +-- answer_bank.py")
        print("  +-- cli.py")
        print("  +-- __init__.py")
        print("  +-- main.py")
        print("  +-- evaluation/")
        print("      +-- __init__.py")
        print("      +-- evaluator.py")
        print("      +-- model_loader.py")
        print("      +-- video_processor.py")
        print("      +-- run_evaluation.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())