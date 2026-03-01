#!/usr/bin/env python
"""
Generate preview images for seaborn styles.
Run this once to create the preview images.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# Styles to generate previews for
STYLES = ["whitegrid", "darkgrid", "white", "dark", "ticks"]

# Create output directory
output_dir = "src/ktfigure/images"
os.makedirs(output_dir, exist_ok=True)

# Generate sample data
np.random.seed(42)
x = np.random.randn(50)
y = 2 * x + np.random.randn(50)
categories = np.random.choice(['A', 'B', 'C'], 50)

for style in STYLES:
    print(f"Generating preview for {style}...")
    
    # Set the style
    sns.set_style(style)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(3, 2), dpi=96)
    
    # Create scatter plot with multiple colors
    for cat in ['A', 'B', 'C']:
        mask = categories == cat
        ax.scatter(x[mask], y[mask], label=cat, alpha=0.7, s=40)
    
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_title(f'{style.title()} Style', fontsize=10)
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Tight layout
    plt.tight_layout()
    
    # Save
    output_path = os.path.join(output_dir, f"style_preview_{style}.png")
    plt.savefig(output_path, dpi=96, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved to {output_path}")

print("\nAll style previews generated successfully!")
