import pandas as pd
import datetime
import time
import random
import requests
from bs4 import BeautifulSoup
import PyPDF2
import io
import re
from fuzzywuzzy import fuzz

# Constants
DEFAULT_ARTICLE_AGE = 7
MAX_RETRIES = 10
BASE_DELAY = 0.33
MAX_DELAY = 15


class ArticleResource:
    def __init__(self, user_input):
        self.articles_df = pd.DataFrame()
        self.today = datetime.date.today()
        self.time_constraint = self.today - datetime.timedelta(days=DEFAULT_ARTICLE_AGE)
        self.user_input = user_input

    
    def _is_duplicate_title(self, new_title, seen_titles):
        if not new_title or not seen_titles:
            return False

        # Normalize the new title
        new_title = new_title.lower().strip()

        # Check for exact match first (faster)
        if new_title in seen_titles:
            return True

        # Check for fuzzy matches
        for seen_title in seen_titles:
            # Use token sort ratio to handle word order differences
            ratio = fuzz.token_sort_ratio(new_title, seen_title)
            if ratio >= self.fuzzy_threshold:
                self.logger.info(f"Fuzzy match found: '{new_title}' matches '{seen_title}' with ratio {ratio}")
                return True

        return False
    
    def get_document_text(self, url):
        try:
            response = self.fetch_with_retry(requests.get, url)
            
            if response.status_code == 200:
                # For PDF content
                if 'pdf' in url:
                    text = self._extract_text_from_pdf(response.content)
                else:
                    text = self._extract_text_from_html(response.text)
                
                # Clean the extracted text
                return self._clean_text(text)
            else:
                self.logger.error(f"Failed to retrieve document: {response.status_code}")
                return f"Failed to retrieve document: {response.status_code}"
                
        except Exception as e:
            self.logger.error(f"Error retrieving document: {e}")
            return f"Error retrieving document: {e}"


    def _extract_text_from_html(self, html_content):
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script_or_style in soup(["script", "style"]):
                script_or_style.extract()
            
            # Get text content
            text = soup.get_text()

            # Get links
            links = soup.find_all('a')

            for link in links:
                link = link.get('href')
                if 'pdf' in link:
                    try:
                        response = requests.get(link)
                        if response.status_code == 200:
                            text += f"\n{self._extract_text_from_pdf(response.content)}"
                        else:
                            self.logger.error(f"Failed to retrieve linked document: {response.status_code}")
                    except Exception as e:
                        self.logger.error(f"Error retrieving linked document: {e}")

            
            # Clean up text: break into lines and remove leading/trailing space
            lines = (line.strip() for line in text.splitlines())
            
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            
            # Remove blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            self.logger.error(f"Error extracting text from HTML: {e}")
            return html_content  # Return original content as fallback
    
    def _extract_text_from_pdf(self, pdf_content):
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                self.logger.warning("PDF is encrypted, cannot extract text")
                return "PDF is encrypted, cannot extract text"
            
            # Extract text from all pages
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            
            return text
            
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {e}")
            return "Error extracting text from PDF"

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

    def fetch_with_retry(self, func, *args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                time.sleep(min(BASE_DELAY * 2 ** attempt + random.uniform(0, 1), MAX_DELAY))