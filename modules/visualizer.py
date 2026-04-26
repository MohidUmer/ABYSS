import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tldextract
import logging
from wordcloud import WordCloud

def generate_browser_visuals(browser_df, browser_name, output_dir):
    """Generates advanced behavioral analytics per browser."""
    if browser_df.empty:
        return
        
    try:
        # Pre-process Timestamp
        browser_df['RealTime'] = pd.to_datetime(browser_df['Timestamp'], errors='coerce')
        
        generate_domain_frequency(browser_df, browser_name, output_dir)
        generate_activity_heatmap(browser_df, browser_name, output_dir)
        generate_protocol_distribution(browser_df, browser_name, output_dir)
        generate_category_cloud(browser_df, browser_name, output_dir)
    except Exception as e:
        logging.error(f"Failed to generate visuals for {browser_name}: {e}")

def generate_domain_frequency(df, browser_name, output_dir):
    try:
        def get_root_domain(url):
            try:
                ext = tldextract.extract(str(url))
                if ext.domain: return f"{ext.domain}.{ext.suffix}"
                return url
            except:
                return str(url)[:30]
                
        df['RootDomain'] = df['Content'].apply(get_root_domain)
        top_domains = df['RootDomain'].value_counts().head(10)
        
        plt.figure(figsize=(10, 6))
        sns.barplot(x=top_domains.values, y=top_domains.index, palette="mako")
        plt.title(f'{browser_name}: Top 10 Domains')
        plt.xlabel('Frequency')
        plt.ylabel('Domain')
        plt.tight_layout()
        
        out_path = os.path.join(output_dir, f"{browser_name}_Domain_Freq.png")
        plt.savefig(out_path, dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        logging.error(f"Error in Domain Freq ({browser_name}): {e}")

def generate_activity_heatmap(df, browser_name, output_dir):
    try:
        time_df = df.dropna(subset=['RealTime']).copy()
        if time_df.empty: return
            
        time_df['Hour'] = time_df['RealTime'].dt.hour
        time_df['DayOfWeek'] = time_df['RealTime'].dt.day_name()
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        time_df['DayOfWeek'] = pd.Categorical(time_df['DayOfWeek'], categories=days, ordered=True)
        
        heatmap_data = time_df.groupby(['DayOfWeek', 'Hour'], observed=False).size().unstack(fill_value=0)
        
        plt.figure(figsize=(12, 6))
        for i in range(24):
            if i not in heatmap_data.columns: heatmap_data[i] = 0
        heatmap_data = heatmap_data[range(24)]
        
        sns.heatmap(heatmap_data, cmap="rocket_r", linewidths=.5, cbar_kws={'label': 'Activity Count'})
        plt.title(f'{browser_name}: Activity Heatmap')
        plt.xlabel('Hour of Day (0-23)')
        plt.ylabel('Day of Week')
        plt.tight_layout()
        
        out_path = os.path.join(output_dir, f"{browser_name}_Activity_Heatmap.png")
        plt.savefig(out_path, dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        logging.error(f"Error in Activity Heatmap ({browser_name}): {e}")

def generate_protocol_distribution(df, browser_name, output_dir):
    try:
        def get_protocol(url):
            url_str = str(url).lower()
            if url_str.startswith("https"): return "HTTPS"
            elif url_str.startswith("http"): return "HTTP"
            elif url_str.startswith("file"): return "Local File"
            else: return "Other"
            
        df['Protocol'] = df['Content'].apply(get_protocol)
        counts = df['Protocol'].value_counts()
        
        plt.figure(figsize=(6, 6))
        plt.pie(counts.values, labels=counts.index, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("pastel"))
        plt.title(f'{browser_name}: Protocol Distribution')
        
        out_path = os.path.join(output_dir, f"{browser_name}_Protocol_Dist.png")
        plt.savefig(out_path, dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        logging.error(f"Error in Protocol Dist ({browser_name}): {e}")

def generate_category_cloud(df, browser_name, output_dir):
    try:
        text = " ".join(str(title) for title in df['Title/Extra'] if str(title).lower() != "n/a")
        if not text.strip(): return
        
        wordcloud = WordCloud(width=800, height=400, background_color='#0A0A0F', colormap='cool').generate(text)
        
        plt.figure(figsize=(10, 5))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(f'{browser_name}: Search & Title Category Cloud', color='white')
        
        # Keep plot background dark
        fig = plt.gcf()
        fig.patch.set_facecolor('#0A0A0F')
        
        out_path = os.path.join(output_dir, f"{browser_name}_Category_Cloud.png")
        plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='#0A0A0F')
        plt.close()
    except Exception as e:
        logging.error(f"Error in Category Cloud ({browser_name}): {e}")
