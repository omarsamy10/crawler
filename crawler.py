#!/usr/bin/env python3

import argparse
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from urllib.parse import urlparse, parse_qs, urljoin
import requests
import json
import time
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver(headless=False):
    """Initialize a browser driver with fallback."""
    try:
        chrome_options = ChromeOptions()
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        if headless:
            chrome_options.add_argument("--headless")
        return webdriver.Chrome(options=chrome_options)
    except Exception as e:
        logger.warning(f"Chrome WebDriver failed: {str(e)}. Falling back to Firefox.")
        try:
            firefox_options = FirefoxOptions()
            firefox_options.set_capability("moz:firefoxOptions", {"prefs": {"devtools.console.stdout.content": True}})
            if headless:
                firefox_options.add_argument("--headless")
            return webdriver.Firefox(options=firefox_options)
        except Exception as e:
            logger.error(f"Firefox WebDriver failed: {str(e)}. No browser available.")
            raise Exception("No supported browser WebDriver found.")

def is_valid_url(url, base_domain):
    """Validate if a URL is a legitimate endpoint."""
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ["http", "https"]:
            return False
        if base_domain not in parsed_url.netloc:
            return False
        path = parsed_url.path
        if not path or path == "/":
            return True
        if not re.match(r'^/[a-zA-Z0-9\-_/]*$', path):
            return False
        exclude_extensions = r'\.(css|js|ico|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot|map|txt|xml|pdf)$'
        if re.search(exclude_extensions, path, re.IGNORECASE):
            return False
        invalid_patterns = [
            r'function\(', r'\}\}', r'\|\|', r'\(\s*\)', r'\[.*\]', r'\{.*\}', r'==',
            r'\?\d+:e=', r'\bvar\b', r'\bif\b', r'\belse\b', r'#\\|\?\$\|', r',Pt=function'
        ]
        full_url = url.lower()
        if any(re.search(pattern, full_url) for pattern in invalid_patterns):
            return False
        query = parsed_url.query
        if query:
            if any(len(value) > 100 or re.search(r'[^a-zA-Z0-9=&%_]', value) for values in parse_qs(query).values() for value in values):
                return False
        return True
    except Exception:
        return False

def extract_parameters(request_body):
    """Extract body parameters."""
    body_params = {}
    if request_body:
        try:
            body_params = json.loads(request_body)
        except (json.JSONDecodeError, TypeError):
            body_params = {"raw_body": request_body}
    return body_params

def extract_form_data(form, driver):
    """Extract form data without submitting."""
    form_data = {}
    try:
        inputs = form.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input[type='email'], input[type='password'], input[type='number'], textarea")
        selects = form.find_elements(By.TAG_NAME, "select")
        checkboxes = form.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], input[type='radio']")
        
        for input_field in inputs:
            try:
                if input_field.is_displayed() and input_field.is_enabled():
                    name = input_field.get_attribute("name") or f"input_{len(form_data)}"
                    input_type = input_field.get_attribute("type")
                    value = "test"
                    if input_type == "password":
                        value = "Test123!"
                    elif input_type == "number":
                        value = "42"
                    elif input_field.tag_name == "textarea":
                        value = "Sample text"
                    input_field.send_keys(value)
                    form_data[name] = value
            except Exception as e:
                logger.warning(f"Error processing input field: {str(e)}")
        
        for select in selects:
            try:
                if select.is_displayed() and select.is_enabled():
                    select_obj = Select(select)
                    name = select.get_attribute("name") or f"select_{len(form_data)}"
                    options = select_obj.options
                    if options:
                        select_obj.select_by_index(len(options) - 1)
                        selected_option = select_obj.first_selected_option
                        form_data[name] = selected_option.get_attribute("value")
            except Exception as e:
                logger.warning(f"Error processing dropdown: {str(e)}")
        
        for checkbox in checkboxes:
            try:
                if checkbox.is_displayed() and checkbox.is_enabled():
                    name = checkbox.get_attribute("name") or f"checkbox_{len(form_data)}"
                    if not checkbox.is_selected():
                        checkbox.click()
                    form_data[name] = checkbox.get_attribute("value") or "on"
            except Exception as e:
                logger.warning(f"Error processing checkbox/radio: {str(e)}")
        
        action = form.get_attribute("action")
        method = form.get_attribute("method") or "POST"
        base_url = driver.current_url
        full_url = urljoin(base_url, action) if action else base_url
        
        return {
            "url": full_url,
            "method": method.upper(),
            "body_params": form_data,
            "extra_headers": {}
        }
    except Exception as e:
        logger.error(f"Error extracting form data: {str(e)}")
        return None

def extract_endpoints_from_js(js_content, base_url):
    """Extract valid endpoints from JavaScript content with method inference."""
    endpoints = []
    path_pattern = r'(?:https?:\/\/[^"\s]+)|(?:/[^"\s/][^"\s]*?/[^"\s/][^\s"]*)'
    quoted_path_pattern = r'[\'"](?:https?:\/\/[^"\s]+|/[^"\s/][^"\s]*?/[^"\s/][^\s"]*)[\'"]'
    
    paths = re.findall(path_pattern, js_content) + re.findall(quoted_path_pattern, js_content)
    
    base_domain = urlparse(base_url).netloc
    for path in paths:
        path = path.strip('"\'')
        full_url = urljoin(base_url, path)
        if is_valid_url(full_url, base_domain):
            method = "GET"
            if re.search(r'\.post\s*\(', js_content, re.IGNORECASE) or re.search(r'method:\s*[\'"]POST[\'"]', js_content, re.IGNORECASE):
                method = "POST"
            elif re.search(r'\.put\s*\(', js_content, re.IGNORECASE) or re.search(r'method:\s*[\'"]PUT[\'"]', js_content, re.IGNORECASE):
                method = "PUT"
            elif re.search(r'\.delete\s*\(', js_content, re.IGNORECASE) or re.search(r'method:\s*[\'"]DELETE[\'"]', js_content, re.IGNORECASE):
                method = "DELETE"
            endpoints.append({"url": full_url, "method": method})
    
    return endpoints

def crawl_website(url, headers, max_pages, output_file, headless):
    """Crawl a website and extract endpoints."""
    driver = get_driver(headless)
    endpoints = []
    visited_urls = set()
    urls_to_visit = [url]
    base_domain = urlparse(url).netloc
    js_urls = set()
    
    basic_headers = {
        'Host', 'Connection', 'User-Agent', 'Accept', 'Accept-Encoding', 
        'Accept-Language', 'Content-Length', 'Content-Type', 'Origin', 
        'Referer', 'Sec-Fetch-Site', 'Sec-Fetch-Mode', 'Sec-Fetch-Dest'
    }
    
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": headers})
        
        while urls_to_visit and len(visited_urls) < max_pages:
            current_url = urls_to_visit.pop(0)
            if current_url in visited_urls:
                continue
            try:
                driver.get(current_url)
                visited_urls.add(current_url)
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to load {current_url}: {str(e)}")
                continue
            try:
                clickable_elements = driver.find_elements(By.CSS_SELECTOR, "button, input[type='button'], [onclick]")
                for element in clickable_elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            element.click()
                            time.sleep(1)
                    except Exception as e:
                        logger.warning(f"Error clicking element: {str(e)}")
                forms = driver.find_elements(By.CSS_SELECTOR, "form")
                for form in forms:
                    try:
                        if form.is_displayed():
                            form_data = extract_form_data(form, driver)
                            if form_data and is_valid_url(form_data["url"], base_domain):
                                form_data["extra_headers"] = headers
                                endpoints.append(form_data)
                    except Exception as e:
                        logger.warning(f"Error processing form: {str(e)}")
                search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search']")
                for input_field in search_inputs:
                    try:
                        if input_field.is_displayed() and input_field.is_enabled():
                            input_field.send_keys("test")
                            input_field.send_keys(Keys.RETURN)
                            time.sleep(1)
                    except Exception as e:
                        logger.warning(f"Error interacting with search bar: {str(e)}")
                event_elements = driver.find_elements(By.CSS_SELECTOR, "[onchange], [oninput]")
                for element in event_elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            if element.tag_name == "input":
                                element.send_keys("test")
                                time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Error triggering event on element: {str(e)}")
            except Exception as e:
                logger.error(f"Error interacting with elements on {current_url}: {str(e)}")
            try:
                logs = driver.get_log("performance")
                for entry in logs:
                    try:
                        message = json.loads(entry["message"])["message"]
                        if message["method"] == "Network.requestWillBeSent":
                            request = message["params"]["request"]
                            request_url = request["url"]
                            if is_valid_url(request_url, base_domain):
                                body_params = extract_parameters(request.get("postData"))
                                request_headers = {k: v for k, v in request.get("headers", {}).items() if k not in basic_headers}
                                endpoints.append({
                                    "url": request_url,
                                    "method": request["method"],
                                    "body_params": body_params,
                                    "extra_headers": request_headers
                                })
                            if request_url.endswith(".js") and is_valid_url(request_url, base_domain):
                                js_urls.add(request_url)
                    except (KeyError, json.JSONDecodeError) as e:
                        logger.warning(f"Error processing log entry: {str(e)}")
            except Exception as e:
                logger.error(f"Error capturing network logs: {str(e)}")
            try:
                links = driver.find_elements(By.CSS_SELECTOR, "a[href], [href]")
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        parsed_href = urlparse(href)
                        if parsed_href.netloc == base_domain or base_domain in parsed_href.netloc:
                            full_url = urljoin(current_url, href)
                            if is_valid_url(full_url, base_domain) and full_url not in visited_urls and full_url not in urls_to_visit:
                                urls_to_visit.append(full_url)
            except Exception as e:
                logger.error(f"Error extracting links from {current_url}: {str(e)}")
        for js_url in js_urls:
            try:
                response = requests.get(js_url, headers=headers, timeout=5)
                if response.status_code == 200:
                    js_endpoints = extract_endpoints_from_js(response.text, url)
                    for endpoint in js_endpoints:
                        body_params = extract_parameters(None)
                        endpoints.append({
                            "url": endpoint["url"],
                            "method": endpoint["method"],
                            "body_params": body_params,
                            "extra_headers": headers
                        })
            except Exception as e:
                logger.error(f"Error processing JavaScript file {js_url}: {str(e)}")
        unique_endpoints = []
        seen_urls = set()
        for endpoint in endpoints:
            if endpoint["url"] not in seen_urls and is_valid_url(endpoint["url"], base_domain):
                seen_urls.add(endpoint["url"])
                unique_endpoints.append(endpoint)
        try:
            output_format = output_file.split('.')[-1].lower() if '.' in output_file else 'json'
            if output_format == 'json':
                with open(output_file, "w") as f:
                    json.dump(unique_endpoints, f, indent=2)
            elif output_format == 'txt':
                with open(output_file, "w") as f:
                    for endpoint in unique_endpoints:
                        f.write(f"{endpoint['url']}\n")
            elif output_format == 'csv':
                with open(output_file, "w", newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["URL", "Method", "Body Params", "Extra Headers"])
                    for endpoint in unique_endpoints:
                        writer.writerow([
                            endpoint['url'],
                            endpoint['method'],
                            json.dumps(endpoint['body_params']),
                            json.dumps(endpoint['extra_headers'])
                        ])
            else:
                raise ValueError(f"Unsupported output format: {output_format}. Use json, txt, or csv.")
            print(f"Endpoints saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving endpoints: {str(e)}")
        return unique_endpoints
    except Exception as e:
        logger.error(f"Error occurred during crawling: {str(e)}")
        return endpoints
    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser(description="Web crawler to extract endpoints.")
    parser.add_argument("-u", "--url", required=True, help="Starting URL to crawl")
    parser.add_argument("-m", "--max-pages", type=int, default=10, help="Maximum number of pages to crawl")
    parser.add_argument("-o", "--output", default="endpoints.json", help="Output file (json, txt, or csv)")
    parser.add_argument("-f", "--format", choices=['json', 'txt', 'csv'], default='json', help="Output format (json, txt, csv)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--header", action="append", help="Custom header in format 'Key: Value'")

    args = parser.parse_args()

    headers = {}
    if args.header:
        for header in args.header:
            try:
                key, value = header.split(": ", 1)
                headers[key] = value
            except ValueError:
                print(f"Invalid header format: {header}. Use 'Key: Value'")
                return

    # Override output format based on file extension if not specified
    output_format = args.format
    if args.output.split('.')[-1].lower() in ['json', 'txt', 'csv']:
        output_format = args.output.split('.')[-1].lower()

    endpoints = crawl_website(args.url, headers, args.max_pages, args.output, args.headless)
    
    if endpoints:
        print("Captured endpoints:")
        for endpoint in endpoints:
            print(f"URL: {endpoint['url']}")
            print(f"Method: {endpoint['method']}")
            print(f"Body Params: {endpoint['body_params']}")
            print(f"Extra Headers: {endpoint['extra_headers']}")
            print("-" * 50)
    else:
        print("No endpoints captured.")

if __name__ == "__main__":
    main()