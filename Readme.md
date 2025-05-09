# Web Crawler

A Python-based command-line web crawler that uses Selenium to navigate websites, interact with dynamic elements (forms, buttons, search bars), capture network requests, and extract valid endpoints. The crawler saves endpoint details (URL, method, body parameters, headers) to a file in JSON, plain text, or CSV format.

## Features

- Crawls websites starting from a given URL, up to a specified page limit.
- Interacts with dynamic elements:
  - Clicks buttons and submit-like elements.
  - Fills forms (text inputs, dropdowns, checkboxes) without submitting.
  - Enters test data in search bars.
  - Triggers `onchange` and `oninput` events.
- Captures network requests to identify HTTP endpoints.
- Extracts endpoints from JavaScript files.
- Validates URLs to ensure they belong to the base domain and exclude static assets (CSS, JS, images).
- Supports custom HTTP headers (e.g., Authorization tokens).
- Saves unique endpoints to a file in JSON, plain text, or CSV format.
- Browser fallback: Uses Chrome, falls back to Firefox if Chrome is unavailable.
- Accurate HTTP method detection (GET, POST, PUT, DELETE) for all endpoints.

## Warning

**Caution**: This crawler sends real HTTP requests to the target website, interacting with forms, buttons, and search bars. **Do not use this tool with real accounts or credentials**, as it may trigger security measures, lock accounts, or result in bans. Always obtain permission from the website owner before crawling, and use test accounts or environments to avoid unintended consequences.

## Installation

1. **Install Python**: Ensure Python 3.6+ is installed.
2. **Install Dependencies**:
   ```bash
   pip install selenium requests
   ```
3. **Install WebDriver**:
   - For Chrome: Install [ChromeDriver](https://chromedriver.chromium.org/downloads) matching your Chrome version.
   - For Firefox: Install [GeckoDriver](https://github.com/mozilla/geckodriver/releases).
   - Ensure the WebDriver executable is in your system PATH.

## Usage

Run the crawler from the command line using `crawler.py`.

```bash
python crawler.py -u http://example.com -m 10 -o endpoints.json --headless --header "Authorization: Bearer token"
```

### Command-Line Arguments

- `-u/--url`: Starting URL (required).
- `-m/--max-pages`: Maximum pages to crawl (default: 10).
- `-o/--output`: Output file (default: `endpoints.json`).
- `-f/--format`: Output format (`json`, `txt`, `csv`; default: `json` or inferred from file extension).
- `--headless`: Run in headless mode.
- `--header`: Custom header (e.g., `--header "Authorization: Bearer token"`; can be used multiple times).

### Output Formats

- **JSON** (default):
  - Array of objects with `url`, `method`, `body_params`, and `extra_headers`.
  - Example: `endpoints.json`
    ```json
    [
      {
        "url": "http://example.com/api/submit",
        "method": "POST",
        "body_params": {"query": "test"},
        "extra_headers": {"Authorization": "Bearer token"}
      }
    ]
    ```
  - Use case: General-purpose, suitable for scripts or tools that parse JSON.

- **Plain Text (`txt`)**:
  - One URL per line.
  - Example: `endpoints.txt`
    ```
    http://example.com/api/submit
    ```
  - Use case: Direct input to tools like `nuclei`, `ffuf`, or `sqlmap`.

- **CSV**:
  - Columns: `URL`, `Method`, `Body Params` (JSON-serialized), `Extra Headers` (JSON-serialized).
  - Example: `endpoints.csv`
    ```
    URL,Method,Body Params,Extra Headers
    http://example.com/api/submit,POST,"{""query"": ""test""}","{""Authorization"": ""Bearer token""}"
    ```
  - Use case: Structured data for analysis or tools that accept CSV.

## Examples

1. **Basic Crawl with JSON Output**:
   ```bash
   python crawler.py -u http://example.com -m 10 -o endpoints.json --headless
   ```

2. **Crawl with Authentication and Text Output**:
   ```bash
   python crawler.py -u http://example.com -m 20 -o endpoints.txt -f txt --headless --header "Authorization: Bearer eyJhbGciOiJIUzUxMiJ9..."
   ```

3. **Crawl with CSV Output**:
   ```bash
   python crawler.py -u http://example.com -m 15 -o endpoints.csv -f csv --headless --header "User-Agent: Mozilla/5.0"
   ```

4. **Pipe to Nuclei for Vulnerability Scanning**:
   ```bash
   python crawler.py -u http://example.com -o endpoints.txt -f txt --headless
   cat endpoints.txt | nuclei -t /path/to/templates
   ```

5. **Pipe to FFUF for Fuzzing**:
   ```bash
   python crawler.py -u http://example.com -o endpoints.txt -f txt --headless
   ffuf -w endpoints.txt -u FUZZ
   ```

6. **Test SQL Injection with sqlmap**:
   ```bash
   python crawler.py -u http://example.com -o endpoints.txt -f txt --headless
   sqlmap -m endpoints.txt --batch
   ```

## Notes

- **Browser Support**: The crawler tries Chrome first, falling back to Firefox if Chrome is unavailable.
- **HTTP Methods**: Accurately detects GET, POST, PUT, DELETE methods, including for endpoints extracted from JavaScript.
- **Error Handling**: Logs errors and warnings for debugging.
- **Output**: Use the `txt` format for easy integration with most security tools.

## Contributing

Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/YourFeature`).
3. Commit changes (`git commit -m "Add YourFeature"`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request.