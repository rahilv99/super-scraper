"""
Web scraping functionality to extract full article text from URLs
"""
import logging
import re
import time
import random
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

# Constants
MAX_RETRIES = 10
BASE_DELAY = 0.33
MAX_DELAY = 15

class ArticleScraper:
    """
    Web scraping class that extracts full article text from URLs.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('pulse.scraper')
        self.headless = True
        self.timeout = 10
        self.driver = None
    
    def setup_webdriver(self):
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--enable-unsafe-swiftshader")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/90.0.4430.212 Safari/537.36"
            )
            
            # Disable images to speed up loading
            chrome_prefs = {
                "profile.default_content_setting_values": {
                    "images": 2,  # 2 = block images
                    "notifications": 2,  # 2 = block notifications
                    "auto_select_certificate": 2,  # 2 = block certificate selection
                }
            }
            chrome_options.add_experimental_option("prefs", chrome_prefs)
            # Install ChromeDriver and set up the service
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
            return True
        except Exception as e:
            self.logger.error(f"Error setting up WebDriver: {e}")
            return False
    
    def fetch_with_retry(self, func, *args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                time.sleep(min(BASE_DELAY * 2 ** attempt + random.uniform(0, 1), MAX_DELAY))
    
    def get_document_text(self, google_url: str) -> str:
        if not self.driver:
            self.logger.warning("WebDriver not initialized. Initializing...")
            if not self.setup_webdriver():
                self.logger.error("Failed to set up WebDriver. Cannot proceed.")
                return ''

        # Get the final URL
        try:
            # Load the Google News page with a timeout
            try:
                self.driver.get(google_url)
            except TimeoutException:
                self.logger.warning(f"Page load timeout for: {google_url}. Moving to the next link.")
                return ''  # Return original URL on timeout
            except Exception as e:
                self.logger.warning(f"An unexpected error occurred for {google_url}: {e}. Skipping.")
                return ''  # Return original URL on error

            initial_url = google_url
            timeout = 5  # Timeout after 5 seconds
            start_time = time.time()

            # Polling mechanism to monitor redirect
            while True:
                try:
                    current_url = self.driver.current_url
                    if current_url != initial_url:
                        break

                    if time.time() - start_time > timeout:
                        self.logger.warning("Timeout reached while waiting for URL to change.")
                        return ''

                    time.sleep(0.2)  # Check every 0.2 seconds
                except Exception as e:
                    self.logger.warning(f"Error checking current URL: {e}. Continuing with original URL.")
                    return ''

        except Exception as e:
            self.logger.error(f"Error following URL {google_url}: {e}")
            return ''

        try:
            html_content = self.driver.page_source
            if html_content:
                text = self._extract_text_from_html(html_content)
            else:
                self.logger.warning(f"Selenium failed to retrieve document: {current_url}")

                response = self.fetch_with_retry(requests.get, current_url)

                if response.status_code == 200:
                    text = self._extract_text_from_html(response.text)
                else:
                    self.logger.warning(f"Requests failed to retrieve document: {response.status_code}")
                    return "Failed to retrieve document"

            return self._clean_text(text)
        except Exception as e:
            self.logger.warning(f"Error retrieving document: {e}")
            return "Error retrieving document"

    def _extract_text_from_html(self, html_content: str) -> str:
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script_or_style in soup(["script", "style"]):
                script_or_style.extract()

            # Get text content
            text = soup.get_text()

            # Clean up text: break into lines and remove leading/trailing space
            lines = (line.strip() for line in text.splitlines())
            
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            
            # Remove blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            self.logger.info(f"Successfully extracted text from HTML ({len(text)} characters)")
            return text
        except Exception as e:
            self.logger.error(f"Error extracting text from HTML: {e}")
            return html_content  # Return original content as fallback

    
    def _clean_text(self, text):
        """
        Clean extracted text by removing extra spaces, normalizing whitespace,
        handling special characters, and improving readability.
        """
        if not text:
            return ""
            
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        
        # Replace multiple newlines with a single newline
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Fix common PDF extraction issues
        text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)  # Fix hyphenation
        text = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', text)  # Fix decimal numbers
        
        # Replace special characters that might be incorrectly encoded
        text = text.replace('â€™', "'")
        text = text.replace('â€œ', '"')
        text = text.replace('â€', '"')
        text = text.replace('â€"', '-')
        text = text.replace('â€"', '--')
        
        # Remove non-printable characters
        text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
        
        # Trim leading/trailing whitespace
        text = text.strip()
        
        return text
