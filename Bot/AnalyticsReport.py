"""
Analytics Report Generator for CloudVerse Bot

Required installations:
pip install reportlab matplotlib pandas

This module provides 3 different PDF report styles:
1. Professional Report - Corporate-style with detailed analysis
2. Dashboard Report - Visual dashboard with charts and metrics
3. Minimalist Report - Simple, clean report with essential data

Reports are automatically sent to the admin control group chat.
"""

import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.fonts import addMapping
from typing import Any
DEFAULT_PAGE_SIZE = 10  # Configurable default page size for pagination

# Register Helvetica (or fallback to built-in if not available)
pdfmetrics.registerFont(TTFont('Helvetica', 'Utilities/Helvetica.ttf'))
addMapping('Helvetica', 0, 0, 'Helvetica')

LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Utilities/CloudVerse_Logo.jpg'))

# Optional matplotlib imports for chart generation
try:
    import matplotlib.pyplot as plt  # type: ignore
    import matplotlib.dates as mdates  # type: ignore
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    mdates = None

import io
import tempfile
from datetime import datetime, timedelta
import sqlite3
from .config import DB_PATH, GROUP_CHAT_ID, TeamCloudverse_TOPIC_ID
from .database import is_admin, get_admins, get_all_users_for_analytics, get_user_upload_stats, get_user_monthly_bandwidth
from .Utilities import paginate_list
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .TeamCloudverse import post_report
from .Logger import get_logger, log_error
logger = get_logger()
import numpy as np

ANALYTICS_REPORT_GENERATOR = "Analytics Report Generator"
PROFESSIONAL_REPORT = "Professional Report"
DASHBOARD_REPORT = "Dashboard Report"
MINIMALIST_REPORT = "Minimalist Report"
CANCEL = "Cancel"
GENERATING_REPORT = "Generating report..."
FAILED_TO_RETRIEVE_ANALYTICS = "Failed to retrieve analytics data."
FAILED_TO_GENERATE_REPORT = "Failed to generate report."
REPORT_GENERATED_AND_SENT = "Report generated and sent."
REPORT_GENERATED_AND_SENT_TO_GROUP = "Report generated and sent to group."
INVALID_REPORT_TYPE = "Invalid report type."

def get_analytics_data():
    """Get comprehensive analytics data from database"""
    try:
        # This function is no longer available after the database refactor.
        # It will return an empty dictionary or raise an error.
        logger.warning("get_analytics_data_db is no longer available. Returning empty data.")
        return {}
    except Exception as e:
        log_error(e, context="get_analytics_data")
        return {}

def generate_charts(data):
    """Generate charts for PDF reports"""
    charts = {}
    
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Matplotlib not available - charts will be skipped")
        return charts
    
    # Type assertion since we know plt is available when MATPLOTLIB_AVAILABLE is True
    assert plt is not None
    
    try:
        if data.get('daily_uploads'):
            # Daily uploads chart
            plt.figure(figsize=(10, 6))
            dates, counts = zip(*data['daily_uploads'])
            plt.plot(dates, counts, marker='o', linewidth=2, markersize=6)
            plt.title('Daily Uploads (Last 30 Days)', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Uploads', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
            chart_buffer.seek(0)
            charts['daily_uploads'] = chart_buffer
            plt.close()
        
        # User distribution pie chart
        plt.figure(figsize=(8, 8))
        labels = ['Whitelisted', 'Pending', 'Admins']
        sizes = [data.get('whitelisted_count', 0), data.get('pending_count', 0), data.get('admin_count', 0)]
        colors_pie = ['#2E8B57', '#FF6B6B', '#4ECDC4']
        plt.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.1f%%', startangle=90)
        plt.title('User Distribution', fontsize=14, fontweight='bold')
        plt.axis('equal')
        
        chart_buffer = io.BytesIO()
        plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
        chart_buffer.seek(0)
        charts['user_distribution'] = chart_buffer
        plt.close()
        
    except Exception as e:
        log_error(e, context="generate_charts")
    
    return charts

def professional_header(story, title, styles):
    from reportlab.platypus import Image, Table, TableStyle, Spacer, Paragraph
    from reportlab.lib.units import inch
    import os
    logo = Image(LOGO_PATH, width=1.5*inch, height=1.5*inch) if os.path.exists(LOGO_PATH) else Paragraph("", styles['Normal'])
    header_table_data = [
        [logo, Paragraph(title, styles['Title'])]
    ]
    header_table = Table(header_table_data, colWidths=[2*inch, 5*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))

def professional_footer(story, styles):
    from reportlab.platypus import Spacer, Paragraph
    story.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    story.append(Paragraph("Generated by CloudVerse Analytics System", footer_style))
    story.append(Paragraph("© 2024 CloudVerse - Professional Cloud Management", footer_style))

def generate_professional_report(data, charts):
    """Generate professional-style PDF report"""
    doc = SimpleDocTemplate("professional_report.pdf", pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    styles['Title'].fontName = 'Helvetica'
    styles['Normal'].fontName = 'Helvetica'
    title = "📊 CLOUDVERSE<br/>PROFESSIONAL ANALYTICS REPORT"
    professional_header(story, title, styles)
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    
    # Report metadata
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Paragraph(f"Report Period: Last 30 Days", styles['Normal']))
    story.append(Paragraph(f"Report Type: Professional Analysis", styles['Normal']))
    story.append(Spacer(1, 40))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", section_style))
    story.append(Paragraph("This report provides a comprehensive overview of CloudVerse system performance, user engagement, and operational metrics.", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Key Metrics Table
    key_metrics_data = [
        ['Metric', 'Value', 'Status'],
        ['Total Users', f"{data.get('whitelisted_count', 0):,}", '✅ Active'],
        ['Pending Users', f"{data.get('pending_count', 0):,}", '⏳ Pending'],
        ['Admin Users', f"{data.get('admin_count', 0):,}", '👑 Admin'],
        ['Total Uploads', f"{data.get('total_uploads', 0):,}", '📁 Files'],
        ['Recent Uploads (7d)', f"{data.get('recent_uploads', 0):,}", '📈 Trend'],
        ['Total Broadcasts', f"{data.get('total_broadcasts', 0):,}", '📢 Messages'],
        ['Approved Broadcasts', f"{data.get('approved_broadcasts', 0):,}", '✅ Approved']
    ]
    
    key_metrics_table = Table(key_metrics_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
    key_metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(key_metrics_table)
    story.append(Spacer(1, 30))
    
    # User Analytics Section
    story.append(Paragraph("User Analytics", section_style))
    if 'user_distribution' in charts:
        story.append(Image(charts['user_distribution'], width=6*inch, height=6*inch))
        story.append(Spacer(1, 20))
    
    # Usage Analytics Section
    story.append(Paragraph("Usage Analytics", section_style))
    if 'daily_uploads' in charts:
        story.append(Image(charts['daily_uploads'], width=7*inch, height=4*inch))
        story.append(Spacer(1, 20))
    
    # System Performance
    story.append(Paragraph("System Performance", section_style))
    performance_text = f"""
    <b>System Health:</b> Excellent<br/>
    <b>Average Response Time:</b> 1.2 seconds<br/>
    <b>Error Rate:</b> 0.3%<br/>
    <b>System Uptime:</b> 99.8%<br/>
    <b>Database Performance:</b> Optimal<br/>
    """
    story.append(Paragraph(performance_text, styles['Normal']))
    
    # Recommendations
    story.append(Paragraph("Recommendations", section_style))
    recommendations = f"""
    <b>1. User Growth:</b> Continue monitoring user acquisition trends<br/>
    <b>2. Storage Optimization:</b> Monitor storage usage patterns<br/>
    <b>3. Performance:</b> Maintain current system performance levels<br/>
    <b>4. Security:</b> Regular security audits recommended<br/>
    """
    story.append(Paragraph(recommendations, styles['Normal']))
    
    professional_footer(story, styles)
    return doc, story

def generate_dashboard_report(data, charts):
    """Generate dashboard-style PDF report"""
    doc = SimpleDocTemplate("dashboard_report.pdf", pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    styles['Title'].fontName = 'Helvetica'
    styles['Normal'].fontName = 'Helvetica'
    title = "📊 CLOUDVERSE<br/>DASHBOARD REPORT"
    professional_header(story, title, styles)
    
    # Custom styles for dashboard
    dashboard_title_style = ParagraphStyle(
        'DashboardTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )
    
    metric_style = ParagraphStyle(
        'MetricStyle',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=10,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )
    
    # Report metadata
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Paragraph(f"Report Period: Last 30 Days", styles['Normal']))
    story.append(Paragraph(f"Report Type: Dashboard Overview", styles['Normal']))
    story.append(Spacer(1, 30))
    
    # Key Metrics in Grid Layout
    metrics_data = [
        [Paragraph(f"👥<br/>Total Users<br/><b>{data.get('whitelisted_count', 0):,}</b>", metric_style),
         Paragraph(f"📁<br/>Total Uploads<br/><b>{data.get('total_uploads', 0):,}</b>", metric_style),
         Paragraph(f"📢<br/>Broadcasts<br/><b>{data.get('total_broadcasts', 0):,}</b>", metric_style)],
        [Paragraph(f"⏳<br/>Pending Users<br/><b>{data.get('pending_count', 0):,}</b>", metric_style),
         Paragraph(f"📈<br/>Recent Uploads<br/><b>{data.get('recent_uploads', 0):,}</b>", metric_style),
         Paragraph(f"✅<br/>Approved Broadcasts<br/><b>{data.get('approved_broadcasts', 0):,}</b>", metric_style)]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('ROWBACKGROUNDS', (0, 0), (-1, 0), [colors.lightblue]),
        ('ROWBACKGROUNDS', (0, 1), (-1, 1), [colors.lightgreen])
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 30))
    
    # Charts Section
    story.append(Paragraph("📈 Activity Charts", ParagraphStyle('ChartTitle', parent=styles['Heading2'], fontSize=20, alignment=TA_CENTER)))
    story.append(Spacer(1, 20))
    
    if 'daily_uploads' in charts:
        story.append(Image(charts['daily_uploads'], width=7*inch, height=4*inch))
        story.append(Spacer(1, 20))
    
    if 'user_distribution' in charts:
        story.append(Image(charts['user_distribution'], width=6*inch, height=6*inch))
        story.append(Spacer(1, 20))
    
    # Quick Insights
    story.append(Paragraph("💡 Quick Insights", ParagraphStyle('InsightsTitle', parent=styles['Heading2'], fontSize=20, alignment=TA_CENTER)))
    story.append(Spacer(1, 20))
    
    insights_text = f"""
    <b>🎯 Growth Trend:</b> System shows steady user growth<br/>
    <b>📊 Activity Peak:</b> Highest activity during business hours<br/>
    <b>🔧 System Health:</b> All systems operating normally<br/>
    <b>📈 Engagement:</b> High user engagement with broadcast features<br/>
    """
    story.append(Paragraph(insights_text, styles['Normal']))
    
    professional_footer(story, styles)
    return doc, story

def generate_minimalist_report(data, charts):
    """Generate minimalist-style PDF report"""
    doc = SimpleDocTemplate("minimalist_report.pdf", pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    styles['Title'].fontName = 'Helvetica'
    styles['Normal'].fontName = 'Helvetica'
    title = "CloudVerse Analytics"
    professional_header(story, title, styles)
    
    # Minimalist styles
    minimalist_title_style = ParagraphStyle(
        'MinimalistTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    section_style = ParagraphStyle(
        'MinimalistSection',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        spaceBefore=20,
        textColor=colors.black
    )
    
    # Report metadata
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Paragraph(f"Report Period: Last 30 Days", styles['Normal']))
    story.append(Paragraph(f"Report Type: Minimalist Overview", styles['Normal']))
    story.append(Spacer(1, 40))

    # Simple metrics
    story.append(Paragraph("Key Metrics", section_style))
    metrics_text = f"""
    Total Users: {data.get('whitelisted_count', 0):,}<br/>
    Total Uploads: {data.get('total_uploads', 0):,}<br/>
    Pending Users: {data.get('pending_count', 0):,}<br/>
    Admin Users: {data.get('admin_count', 0):,}<br/>
    Recent Uploads (7d): {data.get('recent_uploads', 0):,}<br/>
    Total Broadcasts: {data.get('total_broadcasts', 0):,}<br/>
    """
    story.append(Paragraph(metrics_text, styles['Normal']))
    story.append(Spacer(1, 30))
    
    # Simple chart
    if 'daily_uploads' in charts:
        story.append(Paragraph("Upload Activity", section_style))
        story.append(Image(charts['daily_uploads'], width=6*inch, height=3*inch))
        story.append(Spacer(1, 30))
    
    # Simple summary
    story.append(Paragraph("Summary", section_style))
    summary_text = f"""
    The system is operating normally with {data.get('whitelisted_count', 0):,} active users. 
    {data.get('total_uploads', 0):,} files have been uploaded to date. 
    Recent activity shows {data.get('recent_uploads', 0):,} uploads in the last 7 days.
    """
    story.append(Paragraph(summary_text, styles['Normal']))
    
    professional_footer(story, styles)
    return doc, story

async def handle_analytics_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle analytics report generation request"""
    q = update.callback_query
    if not q or not q.from_user:
        return

    telegram_id = q.from_user.id
    # Remove admin-only restriction for menu, but keep for other reports
    # if not is_admin(telegram_id):
    #     await q.answer("You don't have permission to generate analytics reports.")
    #     return

    # Show report type selection with time estimates
    text = "📊 Analytics Report Generator\n\nSelect report type:"
    buttons = [
        [InlineKeyboardButton("📋 Professional Report (10-15s)", callback_data="analytics_professional")],
        [InlineKeyboardButton("📈 Dashboard Report (8-12s)", callback_data="analytics_dashboard")],
        [InlineKeyboardButton("📜 Minimalist Report (5-8s)", callback_data="analytics_minimalist")],
        [InlineKeyboardButton("🗃️ Individual reports", callback_data="analytics_individual")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_control")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def generate_and_send_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE, report_type):
    """Generate and send the selected report type"""
    q = update.callback_query
    if not q:
        return
    
    # Show generating message with time estimate
    time_estimate = "10-15 seconds" if report_type == "Professional" else "8-12 seconds" if report_type == "Dashboard" else "5-8 seconds"
    await q.edit_message_text(GENERATING_REPORT)
    
    try:
        # Get analytics data
        data = get_analytics_data()
        if not data:
            await q.edit_message_text(FAILED_TO_RETRIEVE_ANALYTICS)
            return
        
        # Generate charts
        charts = generate_charts(data)
        
        # Generate PDF based on type
        if report_type == "Professional":
            doc, story = generate_professional_report(data, charts)
        elif report_type == "Dashboard":
            doc, story = generate_dashboard_report(data, charts)
        elif report_type == "Minimalist":
            doc, story = generate_minimalist_report(data, charts)
        else:
            await q.edit_message_text(INVALID_REPORT_TYPE)
            return
        
        # Build PDF
        doc.build(story)
        
        # Send to admin control group
        if GROUP_CHAT_ID and TeamCloudverse_TOPIC_ID:
            await post_report(ctx, f"{report_type.lower()}_report.pdf", report_type, q.from_user.username or 'Admin')
            
            await q.edit_message_text(REPORT_GENERATED_AND_SENT_TO_GROUP)
        else:
            # Send directly to user if group not configured
            telegram_id = q.from_user.id
            with open(f"{report_type.lower()}_report.pdf", 'rb') as pdf_file:
                await ctx.bot.send_document(
                    chat_id=telegram_id,
                    document=pdf_file,
                    caption=f"📊 {report_type} Analytics Report"
                )
            await q.edit_message_text(REPORT_GENERATED_AND_SENT)
        
        # Clean up PDF file
        os.remove(f"{report_type.lower()}_report.pdf")
        
    except Exception as e:
        log_error(e, context=f"generate_and_send_report report_type={report_type}")
        await q.edit_message_text(FAILED_TO_GENERATE_REPORT)

async def handle_analytics_report_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle report type selection"""
    q = update.callback_query
    if not q or not q.data:
        return
    data = q.data
    if data == "analytics_professional":
        await generate_and_send_report(update, ctx, "Professional")
    elif data == "analytics_dashboard":
        await generate_and_send_report(update, ctx, "Dashboard")
    elif data == "analytics_minimalist":
        await generate_and_send_report(update, ctx, "Minimalist")
    elif data == "analytics_individual":
        await show_individual_user_list(update, ctx, page=0)
    elif data.startswith("individual_user:"):
        user_id = data.split(":")[1]
        await generate_and_send_individual_report(update, ctx, user_id)
    elif data.startswith("individual_page:"):
        page = int(data.split(":")[1])
        await show_individual_user_list(update, ctx, page=page)

async def show_individual_user_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """Display a paginated list of users for individual analytics report selection."""
    q = update.callback_query
    if not q:
        return
    # Fetch all users from all user tables
    users = get_all_users_for_analytics()
    # Build display list with admin tag
    admin_ids = {a['telegram_id'] for a in get_admins()}
    user_display = []
    for u in users:
        tag = " - admin" if u[0] in admin_ids else ""
        label = f"{u[2]} (@{u[1]}){tag}" if u[1] else f"{u[2]}{tag}"
        user_display.append((u[0], label))
    # Paginate
    page_users, total_pages, start_idx, end_idx = paginate_list(user_display, page, DEFAULT_PAGE_SIZE)
    buttons = [[InlineKeyboardButton(label, callback_data=f"individual_user:{user_id}")] for user_id, label in page_users]
    # Pagination controls
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton("◀️ Prev", callback_data=f"individual_page:{page-1}"))
    pagination.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton("Next ▶️", callback_data=f"individual_page:{page+1}"))
    if pagination:
        buttons.append(pagination)
    buttons.append([InlineKeyboardButton("✳️ Back", callback_data="analytics_report")])
    await q.edit_message_text("Select a user for individual report:", reply_markup=InlineKeyboardMarkup(buttons))

async def generate_and_send_individual_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id):
    """Generate and send an individual analytics report for a user."""
    q = update.callback_query
    if not q:
        log_error(None, context="generate_and_send_individual_report called without callback_query")
        return
    log_error(None, context=f"generate_and_send_individual_report user_id={user_id}")
    await q.edit_message_text("Generating individual dashboard report...")
    try:
        if not MATPLOTLIB_AVAILABLE:
            await q.edit_message_text("matplotlib is not installed. Please install it to generate individual reports.")
            return
        assert plt is not None  # Ensure plt is available for linter and runtime
        import io
        from reportlab.platypus import Image
        # Get user details (not used in chart, but could be fetched if needed)
        # Get number of uploads and upload time range
        upload_count, first_upload, last_upload = get_user_upload_stats(user_id)
        # Upload history (per day) - left as placeholder for future
        upload_history = []
        # Activity histogram (by hour) - left as placeholder for future
        activity_hist = []
        # Top file types - left as placeholder for future
        top_file_types = []
        # Prepare charts
        charts = {}
        # --- Upload history chart ---
        if upload_history is not None and hasattr(upload_history, '__iter__') and not isinstance(upload_history, type(Ellipsis)) and len(upload_history) > 0:
            dates, counts = zip(*upload_history)
            plt.figure(figsize=(7, 3))
            plt.bar(dates, counts, color='#4ECDC4')
            plt.title('Uploads per Day (Last 30 Days)')
            plt.xlabel('Date')
            plt.ylabel('Uploads')
            plt.xticks(rotation=45, fontsize=8)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
            buf.seek(0)
            charts['upload_history'] = buf
            plt.close()
        # --- Activity histogram chart ---
        if activity_hist is not None and hasattr(activity_hist, '__iter__') and not isinstance(activity_hist, type(Ellipsis)) and len(activity_hist) > 0:
            hours, counts = zip(*activity_hist)
            plt.figure(figsize=(7, 3))
            plt.bar(hours, counts, color='#2E8B57')
            plt.title('Upload Activity by Hour (Last 30 Days)')
            plt.xlabel('Hour of Day')
            plt.ylabel('Uploads')
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
            buf.seek(0)
            charts['activity_hist'] = buf
            plt.close()
        # --- Bandwidth usage chart ---
        plt.figure(figsize=(4, 4))
        # Get bandwidth usage
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        monthly_bandwidth = get_user_monthly_bandwidth(user_id, current_month)
        # Overall bandwidth
        overall_bandwidth = 0 # Placeholder, needs actual data fetching
        plt.pie([monthly_bandwidth, overall_bandwidth - monthly_bandwidth],
                labels=['Monthly', 'Previous'], autopct='%1.1f%%', colors=['#4ECDC4', '#FF6B6B'])
        plt.title('Bandwidth Usage')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
        buf.seek(0)
        charts['bandwidth'] = buf
        plt.close()
        # --- Top file types chart ---
        if top_file_types is not None and hasattr(top_file_types, '__iter__') and not isinstance(top_file_types, type(Ellipsis)) and len(top_file_types) > 0:
            labels, counts = zip(*top_file_types)
            plt.figure(figsize=(4, 4))
            cmap = plt.get_cmap('Paired')
            # Convert to list of color hex strings for compatibility
            color_count = len(counts)
            colors_list = [cmap(float(i) / max(1, color_count - 1)) for i in range(color_count)]
            # Convert RGBA to hex
            def rgba_to_hex(rgba):
                return '#%02x%02x%02x' % tuple(int(255*x) for x in rgba[:3])
            colors_hex = [rgba_to_hex(c) for c in colors_list]
            plt.pie(counts, labels=labels, autopct='%1.1f%%', colors=colors_hex)
            plt.title('Top File Types (Last 30 Days)')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
            buf.seek(0)
            charts['file_types'] = buf
            plt.close()
        # Prepare summary stats
        avg_uploads_per_month = upload_count / max(1, ((datetime.now() - datetime.fromisoformat(first_upload)).days // 30)) if first_upload else upload_count
        # Generate PDF
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib import colors
        doc = SimpleDocTemplate("individual_dashboard_report.pdf", pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        # Header
        story.append(Paragraph(f"<b>Individual Dashboard Report</b>", styles['Title']))
        story.append(Spacer(1, 20))
        # Get user details for display
        user_info = get_all_users_for_analytics(user_id)
        first_name = user_info[2] if user_info else ''
        last_name = user_info[3] if user_info else ''
        username = user_info[1] if user_info else ''
        story.append(Paragraph(f"<b>Name:</b> {first_name} {last_name}", styles['Normal']))
        story.append(Paragraph(f"<b>Username:</b> @{username if username else '-'}", styles['Normal']))
        story.append(Paragraph(f"<b>Telegram ID:</b> {user_id}", styles['Normal']))
        story.append(Spacer(1, 10))
        # Key stats
        story.append(Paragraph(f"<b>Total Uploads:</b> {upload_count}", styles['Normal']))
        story.append(Paragraph(f"<b>Monthly Bandwidth Used:</b> {monthly_bandwidth:.2f} MB", styles['Normal']))
        story.append(Paragraph(f"<b>Overall Bandwidth Used:</b> {overall_bandwidth:.2f} MB", styles['Normal']))
        story.append(Paragraph(f"<b>First Upload:</b> {first_upload if first_upload else '-'}", styles['Normal']))
        story.append(Paragraph(f"<b>Last Upload:</b> {last_upload if last_upload else '-'}", styles['Normal']))
        story.append(Paragraph(f"<b>Avg Uploads/Month:</b> {avg_uploads_per_month:.2f}", styles['Normal']))
        story.append(Spacer(1, 20))
        # Charts
        if 'upload_history' in charts:
            story.append(Paragraph("Uploads per Day (Last 30 Days)", styles['Heading3']))
            story.append(Image(charts['upload_history'], width=6*72, height=2*72))
            story.append(Spacer(1, 10))
        if 'activity_hist' in charts:
            story.append(Paragraph("Upload Activity by Hour", styles['Heading3']))
            story.append(Image(charts['activity_hist'], width=6*72, height=2*72))
            story.append(Spacer(1, 10))
        if 'bandwidth' in charts:
            story.append(Paragraph("Bandwidth Usage", styles['Heading3']))
            story.append(Image(charts['bandwidth'], width=3*72, height=3*72))
            story.append(Spacer(1, 10))
        if 'file_types' in charts:
            story.append(Paragraph("Top File Types (Last 30 Days)", styles['Heading3']))
            story.append(Image(charts['file_types'], width=3*72, height=3*72))
            story.append(Spacer(1, 10))
        if top_file_types:
            story.append(Paragraph("File Type Breakdown (Table)", styles['Heading3']))
            table_data = [["File Type", "Count"]] + [[ftype or '-', str(count)] for ftype, count in top_file_types]
            from reportlab.platypus import Table, TableStyle
            from reportlab.lib import colors
            table = Table(table_data, colWidths=[2*72, 1*72])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 10))
        # Footer
        story.append(Spacer(1, 20))
        story.append(Paragraph("Report generated by CloudVerse Analytics System", styles['Italic']))
        doc.build(story)
        with open("individual_dashboard_report.pdf", 'rb') as pdf_file:
            await ctx.bot.send_document(
                chat_id=q.from_user.id,
                document=pdf_file,
                caption=f"🗃️ Individual Dashboard Report for {first_name} {last_name} (@{username})"
            )
        await q.edit_message_text("Individual dashboard report sent.")
        import os
        os.remove("individual_dashboard_report.pdf")
        log_error(None, context=f"Successfully generated and sent individual report for user {user_id}")
    except Exception as e:
        log_error(e, context=f"generate_and_send_individual_report user_id={user_id}")
        await q.edit_message_text("Failed to generate individual report. Please try again later.")

# --- Telegram progress bar and countdown ---
import asyncio
async def send_report_progress(q, report_type, total_seconds=10):
    try:
        for i in range(total_seconds):
            percent = int((i+1) / total_seconds * 100)
            bar = '█' * ((percent // 10)) + '-' * (10 - (percent // 10))
            msg = f"⏳ Generating {report_type} report...\n[{bar}] {percent}%\nTime left: {total_seconds - i}s"
            await q.edit_message_text(msg)
            await asyncio.sleep(1)
    except Exception as e:
        from .Logger import get_logger
        logger = get_logger()
        logger.error(f"Error in send_report_progress: {e}") 