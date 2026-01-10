"""
ISO Visualization - Extended NYISOVis for Any ISO

This module extends NYISOToolkit's NYISOVis to work with any ISO
through the ISODataAdapter compatibility layer.
"""

from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from adapters.nyiso_compat import ISODataAdapter, create_iso_data_adapter
from analytics.iso_stat import ISOStat

# Try to import NYISOVis for reference (we'll create our own methods)
try:
    from nyisotoolkit import NYISOVis
    NYISOVIS_AVAILABLE = True
except ImportError:
    NYISOVIS_AVAILABLE = False


class ISOVis:
    """
    Extended visualization class that works with any ISO.
    
    Uses ISODataAdapter to make any ISO data compatible with
    visualization methods inspired by NYISOToolkit's NYISOVis.
    
    Usage:
        # For NYISO
        vis = ISOVis(iso_code='NYISO', year=2024)
        
        # For PJM
        vis = ISOVis(iso_code='PJM', year=2024)
        
        # Generate price PDF
        fig = vis.fig_price_pdf()
        plt.show()
    """
    
    def __init__(
        self,
        iso_code: str,
        year: int,
        out_dir: Optional[Path] = None,
        parquet_base: Optional[Path] = None,
        duckdb_path: Optional[Path] = None,
    ):
        """
        Initialize ISO visualization.
        
        Args:
            iso_code: ISO identifier (NYISO, PJM, etc.)
            year: Year of data
            out_dir: Output directory for saved figures
            parquet_base: Base Parquet directory
            duckdb_path: DuckDB database path
        """
        self.iso_code = iso_code.upper()
        self.year = str(year)
        self.out_dir = out_dir or Path("visualizations")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.parquet_base = parquet_base
        self.duckdb_path = duckdb_path
        self.stat = ISOStat(
            iso_code=iso_code,
            year=int(year),
            parquet_base=parquet_base,
            duckdb_path=duckdb_path,
        )
    
    def fig_price_pdf(
        self,
        dataset: str = 'lbmp_dam_h',
        zones: Optional[list] = None,
        bins: int = 50,
        figsize: tuple = (12, 6),
    ) -> plt.Figure:
        """
        Create price probability density function (PDF) plot.
        
        Args:
            dataset: Dataset name
            zones: List of zones to plot (None = all)
            bins: Number of bins for histogram
            figsize: Figure size
        
        Returns:
            matplotlib Figure
        """
        # Get data
        adapter = create_iso_data_adapter(
            iso_code=self.iso_code,
            dataset=dataset,
            year=int(self.year),
            parquet_base=self.parquet_base,
            duckdb_path=self.duckdb_path,
        )
        
        df = adapter.df
        
        # Filter zones if specified
        if zones:
            df = df.loc[:, [col for col in df.columns if col[1] in zones]]
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot PDF for each zone
        for col in df.columns:
            if isinstance(col, tuple):
                metric, zone = col
            else:
                zone = col
                metric = 'Price'
            
            zone_data = df[col].dropna()
            
            if len(zone_data) > 0:
                ax.hist(
                    zone_data,
                    bins=bins,
                    density=True,
                    alpha=0.6,
                    label=zone,
                )
        
        ax.set_xlabel(f'{metric} ($/MWh)')
        ax.set_ylabel('Probability Density')
        ax.set_title(f'{self.iso_code} Price Distribution - {self.year}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def fig_price_timeseries(
        self,
        dataset: str = 'lbmp_dam_h',
        zones: Optional[list] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        figsize: tuple = (14, 6),
    ) -> plt.Figure:
        """
        Create price time series plot.
        
        Args:
            dataset: Dataset name
            zones: List of zones to plot (None = all)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            figsize: Figure size
        
        Returns:
            matplotlib Figure
        """
        # Get data
        adapter = create_iso_data_adapter(
            iso_code=self.iso_code,
            dataset=dataset,
            year=int(self.year),
            parquet_base=self.parquet_base,
            duckdb_path=self.duckdb_path,
        )
        
        df = adapter.df
        
        # Filter by date range
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # Filter zones if specified
        if zones:
            df = df.loc[:, [col for col in df.columns if col[1] in zones]]
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot time series for each zone
        for col in df.columns:
            if isinstance(col, tuple):
                metric, zone = col
            else:
                zone = col
                metric = 'Price'
            
            zone_data = df[col].dropna()
            
            if len(zone_data) > 0:
                ax.plot(
                    zone_data.index,
                    zone_data.values,
                    label=zone,
                    linewidth=1.5,
                    alpha=0.8,
                )
        
        ax.set_xlabel('Time')
        ax.set_ylabel(f'{metric} ($/MWh)')
        ax.set_title(f'{self.iso_code} Price Time Series - {self.year}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        fig.autofmt_xdate()
        
        plt.tight_layout()
        return fig
    
    def fig_zone_comparison(
        self,
        dataset: str = 'lbmp_dam_h',
        zones: Optional[list] = None,
        figsize: tuple = (12, 8),
    ) -> plt.Figure:
        """
        Create box plot comparing zones.
        
        Args:
            dataset: Dataset name
            zones: List of zones to compare (None = all)
            figsize: Figure size
        
        Returns:
            matplotlib Figure
        """
        # Get data
        adapter = create_iso_data_adapter(
            iso_code=self.iso_code,
            dataset=dataset,
            year=int(self.year),
            parquet_base=self.parquet_base,
            duckdb_path=self.duckdb_path,
        )
        
        df = adapter.df
        
        # Filter zones if specified
        if zones:
            df = df.loc[:, [col for col in df.columns if col[1] in zones]]
        
        # Prepare data for box plot
        data = []
        labels = []
        
        for col in df.columns:
            if isinstance(col, tuple):
                metric, zone = col
            else:
                zone = col
                metric = 'Price'
            
            zone_data = df[col].dropna()
            
            if len(zone_data) > 0:
                data.append(zone_data.values)
                labels.append(zone)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        bp = ax.boxplot(data, labels=labels, patch_artist=True)
        
        # Color boxes
        colors = plt.cm.Set3(np.linspace(0, 1, len(bp['boxes'])))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
        
        ax.set_ylabel('Price ($/MWh)')
        ax.set_title(f'{self.iso_code} Zone Price Comparison - {self.year}')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        return fig
    
    def save_figure(self, fig: plt.Figure, filename: str, format: str = 'png'):
        """
        Save figure to output directory.
        
        Args:
            fig: matplotlib Figure
            filename: Filename (without extension)
            format: File format ('png', 'svg', 'pdf')
        """
        filepath = self.out_dir / f"{filename}.{format}"
        fig.savefig(filepath, format=format, dpi=300, bbox_inches='tight')
        print(f"Saved figure to {filepath}")


def compare_isos_visualization(
    iso_codes: list,
    dataset: str,
    year: int,
    metric: str = 'mean',
    figsize: tuple = (12, 6),
) -> plt.Figure:
    """
    Create comparison visualization across multiple ISOs.
    
    Args:
        iso_codes: List of ISO identifiers
        dataset: Dataset name
        year: Year
        metric: Metric to compare
        figsize: Figure size
    
    Returns:
        matplotlib Figure
    """
    from analytics.iso_stat import compare_isos
    
    # Get comparison data
    comparison_df = compare_isos(iso_codes, dataset, year, metric)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    bars = ax.bar(
        comparison_df['ISO'],
        comparison_df[f'{metric.capitalize()} Price'],
        color=plt.cm.Set3(np.linspace(0, 1, len(comparison_df))),
    )
    
    ax.set_ylabel(f'{metric.capitalize()} Price ($/MWh)')
    ax.set_title(f'ISO Price Comparison - {year}')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.,
            height,
            f'${height:.2f}',
            ha='center',
            va='bottom',
        )
    
    plt.tight_layout()
    return fig

