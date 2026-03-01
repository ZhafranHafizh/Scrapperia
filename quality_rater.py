"""
Quality Rating Module
Modul untuk menilai dan mengurutkan kualitas hasil pencarian
"""

import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import hashlib

class QualityRater:
    def __init__(self):
        # Domain terpercaya berdasarkan bahasa/region
        self.trusted_domains = {
            'id': [
                'kompas.com', 'detik.com', 'tempo.co', 'liputan6.com',
                'tribunnews.com', 'antaranews.com', 'cnn.com', 'bbc.com',
                'cnnindonesia.com', 'katadata.co.id', 'bisnis.com'
            ],
            'en': [
                'bbc.com', 'cnn.com', 'reuters.com', 'ap.org', 'npr.org',
                'theguardian.com', 'nytimes.com', 'washingtonpost.com',
                'bloomberg.com', 'wsj.com', 'forbes.com'
            ],
            'es': [
                'elpais.com', 'elmundo.es', 'lavanguardia.com', 'abc.es',
                'elperiodico.com', 'marca.com'
            ]
        }
        
        # Indikator kualitas berdasarkan bahasa
        self.quality_indicators = {
            'id': {
                'positive': ['eksklusif', 'terbaru', 'breaking', 'update', 'terkini', 'resmi', 'konfirmasi'],
                'negative': ['viral', 'heboh', 'geger', 'menggemparkan', 'clickbait']
            },
            'en': {
                'positive': ['breaking', 'exclusive', 'latest', 'confirmed', 'official', 'update', 'analysis'],
                'negative': ['clickbait', 'shocking', 'unbelievable', 'you won\'t believe']
            }
        }
        
        # Spam domain patterns
        self.spam_patterns = [
            r'\.tk$', r'\.ml$', r'\.ga$', r'\.cf$',  # Free domains
            r'click', r'viral', r'buzz', r'bait'     # Clickbait indicators
        ]
    
    def calculate_quality_score(self, result, keyword, language='en'):
        """
        Hitung skor kualitas komprehensif untuk sebuah hasil pencarian
        
        Args:
            result (dict): Hasil pencarian dengan keys: title, description, link, date, keyword
            keyword (str): Kata kunci pencarian asli
            language (str): Kode bahasa (default: 'en')
            
        Returns:
            dict: Skor kualitas detail dengan breakdown
        """
        # Handle both dict and list input at the top level
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                return {'total_score': 0, 'grade': 'F', 'breakdown': {}}
        elif not isinstance(result, dict):
            return {'total_score': 0, 'grade': 'F', 'breakdown': {}}
        
        scores = {
            'relevance_score': 0,      # 30 poin max
            'content_quality_score': 0, # 25 poin max
            'freshness_score': 0,      # 20 poin max
            'authority_score': 0,      # 15 poin max
            'technical_score': 0,      # 10 poin max
            'total_score': 0,
            'grade': 'F',
            'breakdown': {}
        }
        
        # 1. RELEVANCE SCORE (30 poin max)
        relevance = self._calculate_relevance_score(result, keyword)
        scores['relevance_score'] = relevance
        scores['breakdown']['relevance'] = relevance
        
        # 2. CONTENT QUALITY SCORE (25 poin max)
        content_quality = self._calculate_content_quality_score(result, language)
        scores['content_quality_score'] = content_quality
        scores['breakdown']['content_quality'] = content_quality
        
        # 3. FRESHNESS SCORE (20 poin max)
        freshness = self._calculate_freshness_score(result)
        scores['freshness_score'] = freshness
        scores['breakdown']['freshness'] = freshness
        
        # 4. AUTHORITY SCORE (15 poin max)
        authority = self._calculate_authority_score(result, language)
        scores['authority_score'] = authority
        scores['breakdown']['authority'] = authority
        
        # 5. TECHNICAL SCORE (10 poin max)
        technical = self._calculate_technical_score(result)
        scores['technical_score'] = technical
        scores['breakdown']['technical'] = technical
        
        # Total score
        total = sum([scores['relevance_score'], scores['content_quality_score'], 
                    scores['freshness_score'], scores['authority_score'], scores['technical_score']])
        scores['total_score'] = min(100, total)  # Cap at 100
        
        # Grade assignment
        scores['grade'] = self._assign_grade(scores['total_score'])
        
        return scores
    
    def _calculate_relevance_score(self, result, keyword):
        """Hitung skor relevansi berdasarkan kecocokan keyword (30 poin max)"""
        # Handle both dict and list input
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                return 0
        
        score = 0
        title = (result.get('title') or '').lower()
        description = (result.get('description') or '').lower()
        keyword_lower = keyword.lower()
        keyword_words = keyword_lower.split()
        
        # Exact keyword match in title (15 poin)
        if keyword_lower in title:
            score += 15
        # Partial keyword match in title (10 poin)
        elif any(word in title for word in keyword_words):
            matched_words = sum(1 for word in keyword_words if word in title)
            score += int(10 * (matched_words / len(keyword_words)))
        
        # Keyword in description (8 poin max)
        if keyword_lower in description:
            score += 8
        elif any(word in description for word in keyword_words):
            matched_words = sum(1 for word in keyword_words if word in description)
            score += int(5 * (matched_words / len(keyword_words)))
        
        # Keyword proximity bonus (7 poin max)
        title_words = title.split()
        keyword_positions = []
        for word in keyword_words:
            if word in title_words:
                keyword_positions.append(title_words.index(word))
        
        if len(keyword_positions) > 1:
            max_distance = max(keyword_positions) - min(keyword_positions)
            if max_distance <= 3:  # Words are close together
                score += 7
            elif max_distance <= 6:
                score += 4
            elif max_distance <= 10:
                score += 2
        
        return min(30, score)
    
    def _calculate_content_quality_score(self, result, language):
        """Hitung skor kualitas konten (25 poin max)"""
        # Handle both dict and list input
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                return 0
        
        score = 0
        title = (result.get('title') or '').lower()
        description = (result.get('description') or '').lower()
        
        # Description length and quality (10 poin)
        if description and description != 'no description available':
            desc_length = len(description)
            if desc_length >= 150:
                score += 10
            elif desc_length >= 100:
                score += 7
            elif desc_length >= 50:
                score += 4
            elif desc_length >= 20:
                score += 2
        
        # Title quality (8 poin)
        title_length = len(result.get('title') or '')
        if 30 <= title_length <= 80:  # Optimal title length
            score += 8
        elif 20 <= title_length <= 100:
            score += 5
        elif title_length >= 10:
            score += 2
        
        # Quality indicators (7 poin)
        if language in self.quality_indicators:
            positive_indicators = self.quality_indicators[language]['positive']
            negative_indicators = self.quality_indicators[language]['negative']
            
            # Positive indicators
            positive_count = sum(1 for indicator in positive_indicators 
                               if indicator in title or indicator in description)
            score += min(5, positive_count * 2)
            
            # Negative indicators (penalty)
            negative_count = sum(1 for indicator in negative_indicators 
                               if indicator in title or indicator in description)
            score -= min(3, negative_count * 1)
        
        return max(0, min(25, score))
    
    def _calculate_freshness_score(self, result):
        """Hitung skor kesegaran berdasarkan tanggal (20 poin max)"""
        # Handle both dict and list input
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                return 5
        
        if not result.get('date'):
            return 5  # Default score for no date
        
        try:
            if isinstance(result['date'], str):
                return 5  # If date is string, give default score
            
            now = datetime.now()
            article_date = result['date']
            
            # Remove timezone info for comparison
            if hasattr(article_date, 'tzinfo') and article_date.tzinfo:
                article_date = article_date.replace(tzinfo=None)
            
            time_diff = now - article_date
            days_old = time_diff.days
            hours_old = time_diff.total_seconds() / 3600
            
            if hours_old <= 6:      # Less than 6 hours
                return 20
            elif hours_old <= 24:   # Less than 1 day
                return 18
            elif days_old <= 1:     # 1 day
                return 15
            elif days_old <= 3:     # 3 days
                return 12
            elif days_old <= 7:     # 1 week
                return 10
            elif days_old <= 30:    # 1 month
                return 7
            elif days_old <= 90:    # 3 months
                return 4
            elif days_old <= 365:   # 1 year
                return 2
            else:                   # Older than 1 year
                return 1
                
        except Exception:
            return 5  # Default score if date processing fails
    
    def _calculate_authority_score(self, result, language):
        """Hitung skor otoritas sumber (15 poin max)"""
        # Handle both dict and list input
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                return 0
        
        score = 0
        link = result.get('link') or ''
        
        # Check trusted domains
        if language in self.trusted_domains:
            for domain in self.trusted_domains[language]:
                if domain in link:
                    score += 15
                    break
        
        # Check for spam patterns (penalty)
        for pattern in self.spam_patterns:
            if re.search(pattern, link, re.IGNORECASE):
                score -= 5
                break
        
        # Check domain structure
        if 'https://' in link:
            score += 2
        if not any(pattern in link.lower() for pattern in ['bit.ly', 'tinyurl', 'goo.gl']):
            score += 1  # Not a shortened URL
        
        return max(0, min(15, score))
    
    def _calculate_technical_score(self, result):
        """Hitung skor teknis (10 poin max)"""
        # Handle both dict and list input
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                result = result[0]
            else:
                return 0
        
        score = 0
        
        # Has valid link
        link = result.get('link')
        if link and link != 'No link available' and link.startswith('http'):
            score += 5
        
        # Has description
        description = result.get('description')
        if description and description != 'No description available':
            score += 3
        
        # Has date
        if result.get('date'):
            score += 2
        
        return min(10, score)
    
    def _assign_grade(self, total_score):
        """Assign letter grade based on total score"""
        if total_score >= 90:
            return 'A+'
        elif total_score >= 85:
            return 'A'
        elif total_score >= 80:
            return 'A-'
        elif total_score >= 75:
            return 'B+'
        elif total_score >= 70:
            return 'B'
        elif total_score >= 65:
            return 'B-'
        elif total_score >= 60:
            return 'C+'
        elif total_score >= 55:
            return 'C'
        elif total_score >= 50:
            return 'C-'
        elif total_score >= 40:
            return 'D'
        else:
            return 'F'
    
    def rank_results_by_quality(self, results, keyword, language='en'):
        """
        Urutkan hasil berdasarkan skor kualitas
        
        Args:
            results (list): List hasil pencarian
            keyword (str): Kata kunci pencarian
            language (str): Bahasa target
        
        Returns:
            list: Hasil yang sudah diurutkan dengan skor kualitas
        """
        scored_results = []
        
        for result in results:
            # Handle both dict and list input
            if isinstance(result, list):
                if result and isinstance(result[0], dict):
                    result_dict = result[0]
                else:
                    continue  # Skip invalid entries
            else:
                result_dict = result
            
            quality_data = self.calculate_quality_score(result_dict, keyword, language)
            result_dict['quality_score'] = quality_data['total_score']
            result_dict['quality_grade'] = quality_data['grade']
            result_dict['quality_breakdown'] = quality_data['breakdown']
            scored_results.append(result_dict)
        
        # Sort by quality score (highest first), then by date
        scored_results.sort(key=lambda x: (
            x['quality_score'], 
            x.get('date', datetime.min) if x.get('date') else datetime.min
        ), reverse=True)
        
        return scored_results
    
    def remove_duplicates(self, results, similarity_threshold=0.85):
        """
        Hapus hasil duplikat berdasarkan similarity title
        
        Args:
            results (list): List hasil pencarian
            similarity_threshold (float): Threshold similarity (0-1)
        
        Returns:
            tuple: (unique_results, duplicate_count)
        """
        unique_results = []
        seen_hashes = set()
        duplicate_count = 0
        
        for result in results:
            title = result.get('title', '')
            if not title:
                continue
            
            # Check exact title match
            title_hash = hashlib.md5(title.lower().encode()).hexdigest()
            if title_hash in seen_hashes:
                duplicate_count += 1
                continue
            
            # Check similarity with existing results
            is_duplicate = False
            for existing in unique_results:
                existing_title = existing.get('title', '')
                similarity = SequenceMatcher(None, title.lower(), existing_title.lower()).ratio()
                
                if similarity >= similarity_threshold:
                    duplicate_count += 1
                    is_duplicate = True
                    # Keep the one with higher quality score
                    if result.get('quality_score', 0) > existing.get('quality_score', 0):
                        unique_results.remove(existing)
                        unique_results.append(result)
                        seen_hashes.add(title_hash)
                    break
            
            if not is_duplicate:
                unique_results.append(result)
                seen_hashes.add(title_hash)
        
        return unique_results, duplicate_count

# Fungsi helper untuk digunakan di file utama
def rate_and_rank_results(results, keyword, language='en'):
    """Fungsi wrapper untuk rating dan ranking hasil"""
    rater = QualityRater()
    return rater.rank_results_by_quality(results, keyword, language)

def remove_duplicate_results(results, similarity_threshold=0.85):
    """Fungsi wrapper untuk menghapus duplikat"""
    rater = QualityRater()
    return rater.remove_duplicates(results, similarity_threshold)
