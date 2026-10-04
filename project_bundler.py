import os

# Output file where all project code will be combined
OUTPUT_FILE = "complete_project_source.txt"

# Folders or file extensions to ignore
IGNORE_DIRS = {
    "venv",
    ".git",
    "__pycache__",
    "node_modules",
    "data",
}
ALLOWED_EXTENSIONS = {".py", ".html", ".css", ".js", ".json"}


def bundle_project():
  current_dir = os.path.dirname(os.path.abspath(__file__))
  print(f"[INFO] Bundling project from: {current_dir}")

  total_files = 0

  with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
    for root, dirs, files in os.walk(current_dir):
      # Modify dirs in-place to skip ignored directories
      dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

      for file in files:
        file_ext = os.path.splitext(file)[1].lower()

        # Skip output file itself and non-target extensions
        if file == OUTPUT_FILE or file_ext not in ALLOWED_EXTENSIONS:
          continue

        file_path = os.path.join(root, file)
        relative_path = os.path.relpath(file_path, current_dir)

        print(f"[ADDING] {relative_path}")

        outfile.write(f"\n{'='*80}\n")
        outfile.write(f"FILE: {relative_path}\n")
        outfile.write(f"{'='*80}\n\n")

        try:
          with open(file_path, "r", encoding="utf-8", errors="ignore") as infile:
            outfile.write(infile.read())
          outfile.write("\n\n")
          total_files += 1
        except Exception as e:
          outfile.write(f"[ERROR READING FILE: {e}]\n\n")

  print(
      f"\n[SUCCESS] Bundled {total_files} files successfully into"
      f" '{OUTPUT_FILE}'!"
  )


if __name__ == "__main__":
  bundle_project()