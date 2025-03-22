import os
import requests
import json
from openai import OpenAI
from dotenv import load_dotenv
import re
from typing import Dict, List, Optional

# Load environment variables from .env file
load_dotenv()

# Get the model server type
model_server = os.getenv('MODEL_SERVER', 'GROQ').upper()  # Default to GROQ if not set

if model_server == "OPTOGPT":
    API_KEY = os.getenv('OPTOGPT_API_KEY')
    BASE_URL = os.getenv('OPTOGPT_BASE_URL')
    LLM_MODEL = os.getenv('OPTOGPT_MODEL')

elif model_server == "GROQ":
    API_KEY = os.getenv('GROQ_API_KEY')
    BASE_URL = os.getenv('GROQ_BASE_URL')
    LLM_MODEL = os.getenv('GROQ_MODEL')

elif model_server == "NGU":
    API_KEY = os.getenv('NGU_API_KEY')
    BASE_URL = os.getenv('NGU_BASE_URL')
    LLM_MODEL = os.getenv('NGU_MODEL')

elif model_server == "OPENAI":
    API_KEY = os.getenv('OPENAI_API_KEY')
    BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')  # Default to OpenAI's standard base URL
    LLM_MODEL = os.getenv('OPENAI_MODEL')

else:
    raise ValueError(f"Unsupported MODEL_SERVER: {model_server}")

# Initialize the OpenAI client with custom base URL
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# Define a function to make LLM API calls
def call_llm(messages, tools=None, tool_choice=None):
    """
    Make a call to the LLM API with the specified messages and tools.
    
    Args:
        messages: List of message objects
        tools: List of tool definitions (optional)
        tool_choice: Tool choice configuration (optional)
    
    Returns:
        The API response
    """
    kwargs = {
        "model": LLM_MODEL,
        "messages": messages,
    }

    if tools:
        kwargs["tools"] = tools

    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    try:
        response = client.chat.completions.create(**kwargs)
        return response
    except Exception as e:
        print(f"Error calling LLM API: {e}")
        return None


class LLMContentRepurposer:
    """
    An LLM-powered system that takes long-form blog content and repurposes it into
    different formats: summary, social media posts, and email newsletter.
    """
    
    def __init__(self, blog_post: str):
        """
        Initialize with the blog post content.
        
        Args:
            blog_post: The full text of the blog post
        """
        self.blog_post = blog_post
        self.title = self._extract_title()
        self.sections = self._extract_sections()
        
    def _extract_title(self) -> str:
        """Extract the title from the blog post."""
        lines = self.blog_post.strip().split('\n')
        for line in lines:
            line = line.strip()
            # Assume the title is either the first non-empty line
            # or a line starting with # in markdown
            if line and (line.startswith('# ') or lines.index(line) == 0):
                return line.lstrip('# ')
        return "Untitled Blog Post"
    
    def _extract_sections(self) -> Dict[str, str]:
        """
        Extract sections from the blog post.
        Returns a dictionary of section headings and their content.
        """
        sections = {}
        current_section = "Introduction"
        current_content = []
        
        lines = self.blog_post.strip().split('\n')
        for line in lines:
            # Skip the title line
            if line.strip() == f"# {self.title}":
                continue
                
            # Check if line is a section heading (markdown style)
            if re.match(r'^##\s+', line):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Add the last section
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
            
        return sections
    
    def create_summary_with_llm(self, max_length: int = 250) -> str:
        """
        Create a concise summary of the blog post using an LLM.
        
        Args:
            max_length: Maximum character length for the summary
            
        Returns:
            A summary of the blog post
        """
        prompt = f"""
        Create a concise summary of the following blog post. The summary should capture the main points 
        and be around {max_length} characters.
        
        Blog Title: {self.title}
        
        Blog Content:
        {self.blog_post}
        
        Summary:
        """
        
        messages = [
            {"role": "system", "content": "You are an expert content writer who specializes in creating concise, engaging summaries."},
            {"role": "user", "content": prompt}
        ]
        
        response = call_llm(messages)
        
        if response and response.choices:
            summary = response.choices[0].message.content.strip()
            
            # Ensure the summary isn't too long
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."
                
            return summary
        else:
            # Fallback to rule-based summary if LLM call fails
            return self._create_rule_based_summary(max_length)
    
    def _create_rule_based_summary(self, max_length: int = 250) -> str:
        """Fallback method for summary creation if LLM call fails."""
        intro = self.sections.get("Introduction", "")
        if intro:
            intro_paragraph = intro.split('\n\n')[0]
        else:
            intro_paragraph = self.blog_post.split('\n\n')[0]
        
        summary = f"{self.title}\n\n{intro_paragraph}\n\n"
        
        # Add key points from each section
        for section_title, content in self.sections.items():
            if section_title == "Introduction":
                continue  # Skip intro as we already used it
                
            # Get first sentence from section
            sentences = content.split('.')
            if sentences:
                first_sentence = f"{sentences[0]}."
                summary += f"• {section_title}: {first_sentence}\n"
        
        # Trim if necessary
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
            
        return summary
    
    def create_social_media_posts_with_llm(self, platforms: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """
        Create platform-specific social media posts using an LLM.
        
        Args:
            platforms: List of platforms to create posts for.
            
        Returns:
            Dictionary mapping platform names to lists of post content
        """
        if platforms is None:
            platforms = ["twitter", "linkedin", "facebook"]
            
        result = {}
        
        for platform in platforms:
            # Create platform-specific prompt
            if platform == "twitter":
                character_limit = 280
                prompt = f"""
                Create 3 engaging Twitter posts about this blog article. 
                Each post should be under {character_limit} characters including a [LINK] placeholder.
                Include relevant hashtags and make the posts attention-grabbing.
                For one post, include a key statistic or insight from the article.
                
                Blog Title: {self.title}
                
                Blog Content:
                {self.blog_post}
                
                Twitter Posts:
                """
            
            elif platform == "linkedin":
                prompt = f"""
                Create 1 professional LinkedIn post about this blog article.
                The post should be informative, highlight the key points of the article,
                and include relevant industry hashtags at the end.
                Include a [LINK] placeholder where the article link would go.
                
                Blog Title: {self.title}
                
                Blog Content:
                {self.blog_post}
                
                LinkedIn Post:
                """
                
            elif platform == "facebook":
                prompt = f"""
                Create 3 Facebook posts about this blog article:
                1. A conversational main post announcing the article with a brief overview
                2. A quote post that highlights an insightful quote from the article
                3. A post that asks a thought-provoking question related to the article
                
                Include a [LINK] placeholder for all posts.
                
                Blog Title: {self.title}
                
                Blog Content:
                {self.blog_post}
                
                Facebook Posts:
                """
            
            messages = [
                {"role": "system", "content": f"You are an expert social media manager who specializes in creating engaging content for {platform}."},
                {"role": "user", "content": prompt}
            ]
            
            response = call_llm(messages)
            
            if response and response.choices:
                content = response.choices[0].message.content.strip()
                
                # Parse the posts from the LLM response
                # This is a simple approach - might need refinement based on how the LLM structures its response
                posts = [post.strip() for post in content.split("\n\n") if post.strip()]
                
                # Limit to 3 posts per platform
                result[platform] = posts[:3]
            else:
                # Fallback to rule-based post creation if LLM call fails
                result[platform] = self._create_rule_based_social_posts(platform)
                
        return result
    
    def _create_rule_based_social_posts(self, platform: str) -> List[str]:
        """Fallback method for social media post creation if LLM call fails."""
        posts = []
        
        if platform == "twitter":
            # Title post with hashtags
            words = self.title.split()
            hashtags = ' '.join(['#' + word.lower() for word in words if len(word) > 4])
            posts.append(f"{self.title}\n\nNew blog post! Check it out: [LINK]\n\n{hashtags}")
            
        elif platform == "linkedin":
            # More professional, longer content
            main_post = f"📝 New Article: {self.title}\n\n"
            main_post += "I've just published a new blog post exploring:\n\n"
            
            for section, content in self.sections.items():
                first_sentence = content.split('.')[0] + '.'
                main_post += f"• {section}: {first_sentence}\n"
                
            main_post += f"\nCheck out the full article here: [LINK]\n\n"
            main_post += f"#ProfessionalDevelopment #{self.title.split()[0].lower()}"
            posts.append(main_post)
            
        elif platform == "facebook":
            # More conversational
            main_post = f"Just published a new article: '{self.title}'\n\n"
            
            # First paragraph of intro
            intro = self.sections.get("Introduction", "").split('\n\n')[0]
            main_post += f"{intro}\n\n"
            main_post += "In this post, I cover:\n"
            
            for section in self.sections.keys():
                if section != "Introduction":
                    main_post += f"✅ {section}\n"
                    
            main_post += "\nRead the full article here: [LINK]"
            posts.append(main_post)
            
        return posts[:3]  # Limit to 3 posts
    
    def create_email_newsletter_with_llm(self) -> str:
        """
        Create an email newsletter version of the blog post using an LLM.
        
        Returns:
            A formatted email newsletter
        """
        prompt = f"""
        Create an email newsletter to announce this blog post. 
        The newsletter should include:
        1. A compelling subject line
        2. A friendly introduction
        3. A brief overview of the article
        4. A structured table of contents or highlights section
        5. A call to action to read the full article (use [LINK] as a placeholder)
        6. A sign-off with a personal touch
        
        Blog Title: {self.title}
        
        Blog Content:
        {self.blog_post}
        
        Email Newsletter:
        """
        
        messages = [
            {"role": "system", "content": "You are an expert email marketer who specializes in creating engaging newsletters that drive clicks."},
            {"role": "user", "content": prompt}
        ]
        
        response = call_llm(messages)
        
        if response and response.choices:
            newsletter = response.choices[0].message.content.strip()
            return newsletter
        else:
            # Fallback to rule-based newsletter if LLM call fails
            return self._create_rule_based_newsletter()
    
    def _create_rule_based_newsletter(self) -> str:
        """Fallback method for newsletter creation if LLM call fails."""
        newsletter = f"""
Subject: New Blog Post: {self.title}

Dear Subscriber,

I hope this email finds you well! I'm excited to share my latest blog post with you:

## {self.title}

"""
        
        # Add introduction
        intro = self.sections.get("Introduction", "").split('\n\n')[0]
        newsletter += f"{intro}\n\n"
        
        # Add table of contents
        newsletter += "In this article, you'll learn about:\n\n"
        for i, section in enumerate(self.sections.keys()):
            if section != "Introduction":
                newsletter += f"{i}. {section}\n"
        
        newsletter += "\n## Highlights\n\n"
        
        # Add section highlights
        for section, content in self.sections.items():
            if section != "Introduction":
                sentences = content.split('.')
                if len(sentences) > 1:
                    highlight = f"{sentences[0]}.{sentences[1]}."
                else:
                    highlight = content
                    
                if len(highlight) > 200:
                    highlight = highlight[:197] + "..."
                    
                newsletter += f"**{section}**: {highlight}\n\n"
        
        # Call to action
        newsletter += """
## Read the Full Article

To read the complete article, click here: [LINK]

I'd love to hear your thoughts! Feel free to reply to this email with your comments or questions.

Until next time,
[Your Name]

P.S. If you found this valuable, please consider sharing it with a friend or colleague who might also benefit.
"""
        
        return newsletter.strip()
    
    def repurpose_content_with_llm(self) -> Dict:
        """
        Generate all repurposed content formats using LLM assistance.
        
        Returns:
            Dictionary containing all repurposed content
        """
        return {
            "title": self.title,
            "summary": self.create_summary_with_llm(),
            "social_media_posts": self.create_social_media_posts_with_llm(),
            "email_newsletter": self.create_email_newsletter_with_llm()
        }


def repurpose_blog_content_with_llm(blog_post: str) -> Dict:
    """
    Main function to repurpose blog content into multiple formats using LLM assistance.
    
    Args:
        blog_post: The full text of the blog post
        
    Returns:
        Dictionary containing the repurposed content in different formats
    """
    repurposer = LLMContentRepurposer(blog_post)
    return repurposer.repurpose_content_with_llm()


# Example usage
if __name__ == "__main__":
    sample_blog_post = """# The Future of Artificial Intelligence in Healthcare
    
## Introduction

Artificial intelligence (AI) is revolutionizing the healthcare industry, offering innovative solutions to long-standing challenges. From diagnostics to treatment plans, AI technologies are being integrated into various aspects of healthcare delivery. These advancements promise to improve patient outcomes, reduce costs, and enhance operational efficiency.

The rapid development of machine learning algorithms, coupled with the increasing availability of healthcare data, has created unprecedented opportunities for AI applications in medicine. Healthcare providers, researchers, and technology companies are collaborating to harness this potential.

## Diagnostic Applications

One of the most promising applications of AI in healthcare is in diagnostics. Machine learning algorithms can analyze medical images such as X-rays, MRIs, and CT scans with remarkable accuracy. In some cases, AI systems have demonstrated the ability to detect conditions like cancer at earlier stages than human radiologists.

Computer vision technologies can identify subtle patterns that might be missed by the human eye. For example, AI systems can detect minute changes in skin lesions that could indicate melanoma, potentially saving lives through early intervention.

## Treatment Planning

AI is also transforming treatment planning by analyzing vast amounts of patient data to recommend personalized treatment options. These systems can consider a patient's medical history, genetic information, lifestyle factors, and responses to previous treatments.

By processing this comprehensive data, AI can help clinicians develop more effective treatment plans. This is particularly valuable in complex cases where multiple treatment options exist, or when standard approaches have been unsuccessful.

## Healthcare Administration

Beyond clinical applications, AI is streamlining healthcare administration. Natural language processing (NLP) technologies can extract relevant information from electronic health records, reducing the documentation burden on healthcare providers.

AI-powered scheduling systems can optimize appointment times, reducing wait times for patients and improving facility utilization. Similarly, predictive analytics can help hospitals manage inventory and staffing levels more efficiently.

## Challenges and Ethical Considerations

Despite its promise, the integration of AI in healthcare faces significant challenges. Data privacy concerns, algorithmic bias, and questions about liability when AI systems make errors are critical issues that must be addressed.

Healthcare organizations must implement robust governance frameworks to ensure AI systems are used ethically and responsibly. This includes transparent documentation of AI algorithms, regular audits for bias, and clear protocols for human oversight.

## Conclusion

The future of AI in healthcare is bright, with potential benefits for patients, providers, and healthcare systems. As technology continues to evolve, collaboration between technologists, healthcare professionals, ethicists, and policymakers will be essential to realize the full potential of AI while mitigating risks.

By thoughtfully integrating AI into healthcare practices, we can work toward a future where healthcare is more precise, accessible, and patient-centered than ever before.
"""
    
    results = repurpose_blog_content_with_llm(sample_blog_post)
    
    print(f"Title: {results['title']}\n")
    print(f"Summary:\n{results['summary']}\n")
    print("Social Media Posts:")
    for platform, posts in results['social_media_posts'].items():
        print(f"\n{platform.upper()}:")
        for i, post in enumerate(posts, 1):
            print(f"Post {i}:\n{post}\n")
    print(f"Email Newsletter:\n{results['email_newsletter']}")