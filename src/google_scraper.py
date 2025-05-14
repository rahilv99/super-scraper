"""
Google News RSS scraping functionality to get article metadata
"""
import logging
import pandas as pd
from gnews import GNews

logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Constants
DEFAULT_ARTICLE_AGE = 7
MAX_RETRIES = 10
BASE_DELAY = 0.33
MAX_DELAY = 15

from article_resource import ArticleResource

class GoogleNewsScraper(ArticleResource):
    """
    Google News Scraper class that retrieves news article headlines, URL, and metadata.
    """
    def __init__(self, user_topics_output):
        super().__init__(user_topics_output)
        self.logger = logging.getLogger('pulse.gnews') 
        self.fuzzy_threshold = 87
        # Set up GNews parameters
        self.period = '7d'  # Default to 7 days
        self.language = 'en'
        self.country = 'US'
        self.max_results = 100  # Limit results to avoid excessive processing
    
    def get_articles(self):
        """
        Search for news articles related to user topics and store metadata in a DataFrame.
        """
        self.logger.info("Starting Google News article retrieval")
    
        try:
            # Set up GNews
            gnews = GNews(
                language=self.language,
                country=self.country,
                period=self.period,
                max_results=self.max_results
            )
            
            results = []
            
            # Process each user topic
            for topic in self.user_input:
                try:
                    self.logger.info(f"Searching for news articles related to: {topic}")
                    
                    # Get news articles from Google News
                    news_results = self.fetch_with_retry(gnews.get_news, topic)
                    
                    self.logger.info(f"Found {len(news_results)} articles for topic: {topic}")
                    
                    # Process each article
                    seen_titles = []
                    for article in news_results:
                        # Extract article information
                        title = article.get("title", "No title")
                        url = article.get("url", "")
                        publisher = article.get("publisher", {}).get("title", "Unknown")

                        if self._is_duplicate_title(title, seen_titles):
                            self.logger.info(f"Skipping duplicate article: {title}")
                            continue

                        # Add article to results
                        results.append({
                            "title": title,
                            "url": url,
                            "publisher": publisher,
                            "keyword": topic
                        })

                        seen_titles.append(title.lower().strip())
                        
                except Exception as e:
                    self.logger.error(f"Error processing Google News query for {topic}: {e}")
            
            # Create DataFrame and save to CSV
            if results:
                self.logger.info(f"Retrieved {len(results)} Google News articles in total")
                df = pd.DataFrame(results)
                df.drop_duplicates(subset=['title'], inplace=True)
                return df
            else:
                self.logger.warning("No Google News articles found matching the search criteria")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in Google News integration: {e}")
            return None


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example keywords
    keywords = ['Ukraine', 'Defense spending', 'Military']
    
    # Create scraper instance
    scraper = GoogleNewsScraper(keywords)
    
    # Get articles and save to CSV
    df = scraper.get_articles()
    if df is not None:
        df.to_csv('gnews_articles.csv', index=False)
