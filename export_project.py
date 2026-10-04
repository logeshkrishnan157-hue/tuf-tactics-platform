import os

output_file = "full_project_code.txt"
exclude_dirs = {".git", "__pycache__", "venv", "env", "node_modules"}
exclude_extensions = {".png", ".jpg", ".jpeg", ".zip", ".pyc", ".db"}

with open(output_file, "w", encoding="utf-8") as outfile:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if any(file.endswith(ext) for ext in exclude_extensions):
                continue
            file_path = os.path.join(root, file)
            outfile.write(f"\n\n--- FILE START: {file_path} ---\n\n")
            try:
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"[Error reading file: {e}]")
            outfile.write(f"\n\n--- FILE END: {file_path} ---\n\n")

print("Motham project code-um full-a export aayiduchu da!")