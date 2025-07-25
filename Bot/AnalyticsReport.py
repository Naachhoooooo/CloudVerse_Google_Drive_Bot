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
DEFAULT_PAGE_SIZE = 10

pdfmetrics.registerFont(TTFont('Helvetica', 'Utilities/Helvetica.ttf'))
addMapping('Helvetica', 0, 0, 'Helvetica')

LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Utilities/CloudVerse_Logo.jpg'))

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
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
from .database import is_admin, get_admins, get_all_users_for_analytics, get_user_upload_stats, get_user_monthly_bandwidth, get_user_top_file_types, get_user_upload_activity_by_hour, get_user_details_by_id, get_user_total_bandwidth, get_user_uploads_per_day, get_analytics_data
from .Utilities import pagination, handle_errors
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .TeamCloudverse import post_report
import numpy as np

# Message constants (user-facing)
ANALYTICS_REPORT_GENERATOR_TITLE = "📊 Analytics Report Generator\n\nSelect report type:"
PROFESSIONAL_REPORT_BUTTON = "📋 Professional Report (10-15s)"
MINIMALIST_REPORT_BUTTON = "📜 Minimalist Report (5-8s)"
INDIVIDUAL_REPORTS_BUTTON = "🗃️ Individual reports"
CANCEL_BUTTON = "❌ Cancel"
GENERATING_REPORT_MSG = "Generating report..."
FAILED_TO_RETRIEVE_ANALYTICS_MSG = "Failed to retrieve analytics data."
FAILED_TO_GENERATE_REPORT_MSG = "Failed to generate report."
REPORT_GENERATED_AND_SENT_MSG = "Report generated and sent."
REPORT_GENERATED_AND_SENT_TO_GROUP_MSG = "Report generated and sent to group."
INVALID_REPORT_TYPE_MSG = "Invalid report type."
SELECT_USER_FOR_INDIVIDUAL_REPORT_MSG = "Select a user for individual report:"
GENERATING_INDIVIDUAL_REPORT_MSG = "Generating individual dashboard report..."
MATPLOTLIB_NOT_INSTALLED_MSG = "matplotlib is not installed. Please install it to generate individual reports."
INDIVIDUAL_REPORT_SENT_MSG = "Individual dashboard report sent."
FAILED_TO_GENERATE_INDIVIDUAL_REPORT_MSG = "Failed to generate individual report. Please try again later."

def generate_charts(data):
    """Generate charts for PDF reports using matplotlib, if available."""
    charts = {}
    try:
        # Daily uploads chart
        if data.get('daily_uploads'):
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
        # Bandwidth usage chart
        if data.get('bandwidth_usage'):
            plt.figure(figsize=(10, 6))
            dates, bandwidths = zip(*data['bandwidth_usage'])
            bandwidths_mb = [b / (1024 * 1024) for b in bandwidths]
            plt.plot(dates, bandwidths_mb, marker='o', linewidth=2, markersize=6, color='#1a237e')
            plt.title('Bandwidth Usage (Last 30 Days)', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Bandwidth (MB)', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
            chart_buffer.seek(0)
            charts['bandwidth_usage'] = chart_buffer
            plt.close()
        # File type distribution pie chart
        if data.get('file_types'):
            plt.figure(figsize=(8, 8))
            labels, counts = zip(*data['file_types']) if data['file_types'] else ([], [])
            plt.pie(counts, labels=labels, autopct='%1.1f%%', startangle=90)
            plt.title('File Type Distribution (Last 30 Days)', fontsize=14, fontweight='bold')
            plt.axis('equal')
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
            chart_buffer.seek(0)
            charts['file_types'] = chart_buffer
            plt.close()
        # Activity by hour bar chart
        if data.get('activity_by_hour'):
            plt.figure(figsize=(10, 6))
            hours, counts = zip(*data['activity_by_hour'])
            plt.bar(hours, counts, color='#4ECDC4')
            plt.title('Upload Activity by Hour (Last 30 Days)', fontsize=14, fontweight='bold')
            plt.xlabel('Hour of Day', fontsize=12)
            plt.ylabel('Uploads', fontsize=12)
            plt.xticks(range(0, 24))
            plt.tight_layout()
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
            chart_buffer.seek(0)
            charts['activity_by_hour'] = chart_buffer
            plt.close()
        # User growth chart
        if data.get('user_growth'):
            plt.figure(figsize=(10, 6))
            dates, counts = zip(*data['user_growth'])
            plt.plot(dates, counts, marker='o', linewidth=2, markersize=6, color='#2E8B57')
            plt.title('User Growth (Last 30 Days)', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('New Users', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
            chart_buffer.seek(0)
            charts['user_growth'] = chart_buffer
            plt.close()
        # Error rates chart
        if data.get('error_rates'):
            plt.figure(figsize=(10, 6))
            dates, counts = zip(*data['error_rates']) if data['error_rates'] else ([], [])
            plt.plot(dates, counts, marker='o', linewidth=2, markersize=6, color='#FF6B6B')
            plt.title('Error Rates (Last 30 Days)', fontsize=14, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Errors', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=300, bbox_inches='tight')
            chart_buffer.seek(0)
            charts['error_rates'] = chart_buffer
            plt.close()
        # Storage usage (single value, show as text or bar)
        if 'storage_usage' in data:
            charts['storage_usage'] = data['storage_usage']
    except Exception as e:
        print(f"Error in generate_charts: {e}")
    return charts

def professional_header(story, title, styles):
    """Add a professional header with logo and title to the PDF story."""
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

def professional_footer(story, styles, generated_by_name, generated_by_username, timestamp):
    """Add a professional footer to the PDF story with timestamp and generator info."""
    from reportlab.platypus import Spacer, Paragraph
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#888')
    )
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated: {timestamp}", footer_style))
    story.append(Paragraph(f"Generated by: {generated_by_name} (@{generated_by_username})", footer_style))

def minimalist_footer(story, styles, generated_by_name, generated_by_username, timestamp):
    """Add a minimalist footer to the PDF story with timestamp and generator info."""
    from reportlab.platypus import Spacer, Paragraph
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated: {timestamp}", footer_style))
    story.append(Paragraph(f"Generated by: {generated_by_name} (@{generated_by_username})", footer_style))


def generate_professional_report(data, charts, generated_by_name, generated_by_username):
    """Generate a professional-style PDF analytics report with all available analytics and a modern, light/white dashboard template."""
    doc = SimpleDocTemplate("professional_report.pdf", pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    # Modern, light/white dashboard theme
    styles['Title'].fontName = 'Helvetica'
    styles['Normal'].fontName = 'Helvetica'
    styles['Title'].fontSize = 26
    styles['Title'].textColor = colors.HexColor('#1a237e')
    styles['Normal'].fontSize = 12
    styles['Normal'].textColor = colors.HexColor('#222')
    title = "CloudVerse Professional Analytics Dashboard"
    # Header
    story.append(Spacer(1, 16))
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 8))
    # Report metadata
    timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    story.append(Paragraph(f"<b>Report Period:</b> Last 30 Days", styles['Normal']))
    story.append(Paragraph(f"<b>Report Type:</b> Professional Analysis", styles['Normal']))
    story.append(Spacer(1, 18))
    # Key Metrics Table (dashboard style)
    from reportlab.platypus import Table, TableStyle
    metrics_data = [
        ["Total Users", f"{data.get('whitelisted_count', 0):,}"],
        ["Pending Users", f"{data.get('pending_count', 0):,}"],
        ["Admin Users", f"{data.get('admin_count', 0):,}"],
        ["Total Uploads", f"{data.get('total_uploads', 0):,}"],
        ["Recent Uploads (7d)", f"{data.get('recent_uploads', 0):,}"],
        ["Total Broadcasts", f"{data.get('total_broadcasts', 0):,}"],
        ["Approved Broadcasts", f"{data.get('approved_broadcasts', 0):,}"]
    ]
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 1.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f7fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a237e')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f5f7fa'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e3e6ee'))
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 18))
    # User Distribution Pie Chart
    if 'user_distribution' in charts:
        story.append(Paragraph("<b>User Distribution</b>", styles['Normal']))
        story.append(Image(charts['user_distribution'], width=5*inch, height=3*inch))
        story.append(Spacer(1, 12))
    # Daily Uploads Chart
    if 'daily_uploads' in charts:
        story.append(Paragraph("<b>Daily Uploads (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['daily_uploads'], width=6*inch, height=2.5*inch))
        story.append(Spacer(1, 12))
    # Bandwidth Usage Chart
    if 'bandwidth_usage' in charts:
        story.append(Paragraph("<b>Bandwidth Usage (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['bandwidth_usage'], width=6*inch, height=2.5*inch))
        story.append(Spacer(1, 12))
    # File Type Distribution Pie Chart
    if 'file_types' in charts:
        story.append(Paragraph("<b>File Type Distribution (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['file_types'], width=5*inch, height=3*inch))
        story.append(Spacer(1, 12))
    # Activity by Hour Bar Chart
    if 'activity_by_hour' in charts:
        story.append(Paragraph("<b>Upload Activity by Hour (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['activity_by_hour'], width=6*inch, height=2.5*inch))
        story.append(Spacer(1, 12))
    # User Growth Chart
    if 'user_growth' in charts:
        story.append(Paragraph("<b>User Growth (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['user_growth'], width=6*inch, height=2.5*inch))
        story.append(Spacer(1, 12))
    # Error Rates Chart
    if 'error_rates' in charts:
        story.append(Paragraph("<b>Error Rates (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['error_rates'], width=6*inch, height=2.5*inch))
        story.append(Spacer(1, 12))
    # Storage Usage (Single Value)
    if 'storage_usage' in charts:
        story.append(Paragraph("<b>Storage Usage</b>", styles['Normal']))
        story.append(Paragraph(f"{charts['storage_usage']:,}", styles['Normal']))
        story.append(Spacer(1, 12))
    # Recommendations (static)
    recommendations = f"""
    <b>1. User Growth:</b> Continue monitoring user acquisition trends<br/>
    <b>2. Storage Optimization:</b> Monitor storage usage patterns<br/>
    <b>3. Performance:</b> Maintain current system performance levels<br/>
    <b>4. Security:</b> Regular security audits recommended<br/>
    """
    story.append(Paragraph("<b>Recommendations</b>", styles['Normal']))
    story.append(Paragraph(recommendations, styles['Normal']))
    # Footer (timestamp and generator info)
    professional_footer(story, styles, generated_by_name, generated_by_username, timestamp)
    return doc, story

def generate_minimalist_report(data, charts, generated_by_name, generated_by_username):
    """Generate a minimalist-style PDF analytics report with essential data only and a clean, light template."""
    doc = SimpleDocTemplate("minimalist_report.pdf", pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    # Minimalist, light/white theme
    styles['Title'].fontName = 'Helvetica'
    styles['Normal'].fontName = 'Helvetica'
    styles['Title'].fontSize = 22
    styles['Title'].textColor = colors.HexColor('#222')
    styles['Normal'].fontSize = 12
    styles['Normal'].textColor = colors.HexColor('#333')
    title = "CloudVerse Minimalist Analytics"
    # Header
    story.append(Spacer(1, 16))
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 8))
    # Report metadata
    timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    story.append(Paragraph(f"<b>Report Period:</b> Last 30 Days", styles['Normal']))
    story.append(Paragraph(f"<b>Report Type:</b> Minimalist Overview", styles['Normal']))
    story.append(Spacer(1, 18))
    # Key Metrics (summary boxes)
    from reportlab.platypus import Table, TableStyle
    metrics_data = [
        ["Total Users", f"{data.get('whitelisted_count', 0):,}"],
        ["Total Uploads", f"{data.get('total_uploads', 0):,}"],
        ["Pending Users", f"{data.get('pending_count', 0):,}"],
        ["Admin Users", f"{data.get('admin_count', 0):,}"],
        ["Recent Uploads (7d)", f"{data.get('recent_uploads', 0):,}"],
        ["Total Broadcasts", f"{data.get('total_broadcasts', 0):,}"]
    ]
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 1.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#222')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eee'))
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 18))
    # Simple chart (Upload Activity)
    if 'daily_uploads' in charts:
        story.append(Paragraph("<b>Upload Activity (Last 30 Days)</b>", styles['Normal']))
        story.append(Image(charts['daily_uploads'], width=6*inch, height=2.5*inch))
        story.append(Spacer(1, 18))
    # Simple summary
    summary_text = f"""
    <b>System Status:</b> Normal<br/>
    <b>Active Users:</b> {data.get('whitelisted_count', 0):,}<br/>
    <b>Uploads (7d):</b> {data.get('recent_uploads', 0):,}<br/>
    <b>Performance:</b> Stable<br/>
    """
    story.append(Paragraph(summary_text, styles['Normal']))
    # Footer (timestamp and generator info)
    minimalist_footer(story, styles, generated_by_name, generated_by_username, timestamp)
    return doc, story

@handle_errors
async def handle_analytics_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display analytics report options and handle user selection for report type."""
    q = update.callback_query
    if not q or not q.from_user:
        return

    telegram_id = q.from_user.id
    if not is_admin(telegram_id):
        await q.answer("You don't have permission to generate analytics reports.", show_alert=True)
        return

    # Show report type selection with time estimates
    text = ANALYTICS_REPORT_GENERATOR_TITLE
    buttons = [
        [InlineKeyboardButton(PROFESSIONAL_REPORT_BUTTON, callback_data="analytics_professional")],
        [InlineKeyboardButton(MINIMALIST_REPORT_BUTTON, callback_data="analytics_minimalist")],
        [InlineKeyboardButton(INDIVIDUAL_REPORTS_BUTTON, callback_data="analytics_individual")],
        [InlineKeyboardButton(CANCEL_BUTTON, callback_data="admin_control")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@handle_errors
async def generate_and_send_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE, report_type):
    """Generate the selected analytics report type and send it to the user or group."""
    q = update.callback_query
    if not q:
        return
    
    # Show generating message with time estimate
    time_estimate = "10-15 seconds" if report_type == "Professional" else "5-8 seconds"
    await q.edit_message_text(GENERATING_REPORT_MSG)
    
    try:
        # Get analytics data
        data = get_analytics_data()
        if not data:
            await q.edit_message_text(FAILED_TO_RETRIEVE_ANALYTICS_MSG)
            return
        
        # Generate charts
        charts = generate_charts(data)
        
        # Generate PDF based on type
        if report_type == "Professional":
            doc, story = generate_professional_report(data, charts, q.from_user.username or 'Admin', q.from_user.username or 'Admin')
        elif report_type == "Minimalist":
            doc, story = generate_minimalist_report(data, charts, q.from_user.username or 'Admin', q.from_user.username or 'Admin')
        else:
            await q.edit_message_text(INVALID_REPORT_TYPE_MSG)
            return
        
        # Build PDF
        doc.build(story)
        
        # Send to admin control group
        if GROUP_CHAT_ID and TeamCloudverse_TOPIC_ID:
            await post_report(ctx, f"{report_type.lower()}_report.pdf", report_type, q.from_user.username or 'Admin')
            
            await q.edit_message_text(REPORT_GENERATED_AND_SENT_TO_GROUP_MSG)
        else:
            # Send directly to user if group not configured
            telegram_id = q.from_user.id
            with open(f"{report_type.lower()}_report.pdf", 'rb') as pdf_file:
                await ctx.bot.send_document(
                    chat_id=telegram_id,
                    document=pdf_file,
                    caption=f"📊 {report_type} Analytics Report"
                )
            await q.edit_message_text(REPORT_GENERATED_AND_SENT_MSG)
        
        # Clean up PDF file
        os.remove(f"{report_type.lower()}_report.pdf")
        
    except Exception as e:
        print(f"Error in generate_and_send_report report_type={report_type}: {e}")
        await q.edit_message_text(FAILED_TO_GENERATE_REPORT_MSG)

@handle_errors
async def handle_analytics_report_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle the user's selection of analytics report type and trigger report generation."""
    q = update.callback_query
    if not q or not q.data:
        return
    data = q.data
    if data == "analytics_professional":
        await generate_and_send_report(update, ctx, "Professional")
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

@handle_errors
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
    await q.edit_message_text(SELECT_USER_FOR_INDIVIDUAL_REPORT_MSG, reply_markup=InlineKeyboardMarkup(buttons))

@handle_errors
async def generate_and_send_individual_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id):
    """Generate and send an individual analytics report for a specific user using the minimalist template."""
    q = update.callback_query
    if not q:
        print("generate_and_send_individual_report called without callback_query")
        return
    print(f"generate_and_send_individual_report user_id={user_id}")
    await q.edit_message_text(GENERATING_INDIVIDUAL_REPORT_MSG)
    try:
        if not MATPLOTLIB_AVAILABLE:
            await q.edit_message_text(MATPLOTLIB_NOT_INSTALLED_MSG)
            return
        assert plt is not None  # Ensure plt is available for linter and runtime
        import io
        from reportlab.platypus import Image
        # Get number of uploads and upload time range
        upload_count, first_upload, last_upload = get_user_upload_stats(user_id)
        # Upload history (per day)
        upload_history = get_user_uploads_per_day(user_id, days=30)
        # Activity histogram (by hour)
        activity_hist = get_user_upload_activity_by_hour(user_id)
        # Top file types
        top_file_types = get_user_top_file_types(user_id)
        # Prepare charts
        charts = {}
        # --- Upload history chart ---
        if upload_history is not None and hasattr(upload_history, '__iter__') and len(upload_history) > 0:
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
            charts['daily_uploads'] = buf
            plt.close()
        # --- Activity histogram chart ---
        if activity_hist is not None and hasattr(activity_hist, '__iter__') and len(activity_hist) > 0:
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
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        monthly_bandwidth = get_user_monthly_bandwidth(user_id, current_month)
        overall_bandwidth = get_user_total_bandwidth(user_id) / (1024 * 1024)  # MB
        monthly_bandwidth_mb = monthly_bandwidth / (1024 * 1024)
        previous_bandwidth = max(0, overall_bandwidth - monthly_bandwidth_mb)
        plt.pie([monthly_bandwidth_mb, previous_bandwidth],
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
        doc = SimpleDocTemplate("minimalist_report.pdf", pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        # Header
        story.append(Paragraph(f"<b>Individual Dashboard Report</b>", styles['Title']))
        story.append(Spacer(1, 20))
        # Get user details for display
        user_info = get_user_details_by_id(user_id)
        name = user_info['name'] if user_info and 'name' in user_info else ''
        username = user_info['username'] if user_info and 'username' in user_info else ''
        # If name is empty, fallback to first_name/last_name if available
        if not name and user_info:
            name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        story.append(Paragraph(f"<b>Name:</b> {name}", styles['Normal']))
        story.append(Paragraph(f"<b>Username:</b> @{username if username else '-'}", styles['Normal']))
        story.append(Paragraph(f"<b>Telegram ID:</b> {user_id}", styles['Normal']))
        story.append(Spacer(1, 10))
        # Key stats
        story.append(Paragraph(f"<b>Total Uploads:</b> {upload_count}", styles['Normal']))
        story.append(Paragraph(f"<b>Monthly Bandwidth Used:</b> {monthly_bandwidth_mb:.2f} MB", styles['Normal']))
        story.append(Paragraph(f"<b>Overall Bandwidth Used:</b> {overall_bandwidth:.2f} MB", styles['Normal']))
        story.append(Paragraph(f"<b>First Upload:</b> {first_upload if first_upload else '-'}", styles['Normal']))
        story.append(Paragraph(f"<b>Last Upload:</b> {last_upload if last_upload else '-'}", styles['Normal']))
        story.append(Paragraph(f"<b>Avg Uploads/Month:</b> {avg_uploads_per_month:.2f}", styles['Normal']))
        story.append(Spacer(1, 20))
        # Charts
        if 'daily_uploads' in charts:
            story.append(Paragraph("Uploads per Day (Last 30 Days)", styles['Heading3']))
            story.append(Image(charts['daily_uploads'], width=6*72, height=2*72))
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
        with open("minimalist_report.pdf", 'rb') as pdf_file:
            await ctx.bot.send_document(
                chat_id=q.from_user.id,
                document=pdf_file,
                caption=f"🗃️ Individual Dashboard Report for {name} (@{username})"
            )
        await q.edit_message_text(INDIVIDUAL_REPORT_SENT_MSG)
        import os
        os.remove("minimalist_report.pdf")
        print(f"Successfully generated and sent individual report for user {user_id}")
    except Exception as e:
        print(f"Error in generate_and_send_individual_report user_id={user_id}: {e}")
        await q.edit_message_text(FAILED_TO_GENERATE_INDIVIDUAL_REPORT_MSG)

# --- Telegram progress bar and countdown ---
import asyncio
@handle_errors
async def send_report_progress(q, report_type, total_seconds=10):
    """Send progress updates to the user while the report is being generated."""
    try:
        for i in range(total_seconds):
            percent = int((i+1) / total_seconds * 100)
            bar = '█' * ((percent // 10)) + '-' * (10 - (percent // 10))
            msg = f"⏳ Generating {report_type} report...\n[{bar}] {percent}%\nTime left: {total_seconds - i}s"
            await q.edit_message_text(msg)
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error in send_report_progress: {e}") 