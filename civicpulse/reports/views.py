import io
import logging
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from .models import Report
from .ai.classifier import classify_report

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}


def report_to_dict(r):
    return {
        'id': r.id,
        'text': r.text,
        'title': r.title,
        'category': r.category,
        'severity': r.severity,
        'location': r.location,
        'district': r.district,
        'sector': r.sector,
        'cell': r.cell,
        'village': r.village,
        'summary': r.summary,
        'recommended_action': r.recommended_action,
        'status': r.status,
        'priority_score': r.priority_score,
        'confidence': r.confidence,
        'department': r.department,
        'estimated_resolution': r.estimated_resolution,
        'estimated_people_affected': r.estimated_people_affected,
        'public_safety_risk': r.public_safety_risk,
        'economic_impact': r.economic_impact,
        'environmental_impact': r.environmental_impact,
        'urgency': r.urgency,
        'duplicate_detected': r.duplicate_detected,
        'similarity_score': r.similarity_score,
        'similar_report_text': r.similar_report_text,
        'reasoning': r.reasoning,
        'ai_insights': r.ai_insights,
        'keywords': r.keywords,
        'created_at': r.created_at.isoformat(),
    }


# ── /api/reports/ ──────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
def reports(request):
    if request.method == 'GET':
        return Response([report_to_dict(r) for r in Report.objects.all()])

    text = (request.data.get('text') or '').strip()
    if not text:
        return Response({'error': 'text is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        analysis = classify_report(text)
    except Exception as e:
        logger.exception("Classification failed")
        return Response({'error': f'AI classification failed: {e}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # ── Duplicate detection (now also trusts the model's own judgment) ──
    new_cat = analysis.get('category', '')
    new_loc = (analysis.get('location') or '').lower().strip()
    duplicate = None

    if analysis.get('duplicate_detected') and analysis.get('similar_report_text'):
        duplicate = Report.objects.filter(
            summary__icontains=analysis['similar_report_text'][:40]
        ).first()

    if not duplicate and new_loc:
        for existing in Report.objects.filter(category=new_cat, status__in=['open', 'in_progress']):
            existing_loc = (existing.location or '').lower().strip()
            if existing_loc and (existing_loc in new_loc or new_loc in existing_loc):
                duplicate = existing
                break

    report = Report.objects.create(
        text=text,
        title=analysis.get('title', text[:60]),
        category=analysis.get('category', 'Infrastructure'),
        severity=analysis.get('severity', 'Low'),
        location=analysis.get('location'),
        district=analysis.get('district'),
        sector=analysis.get('sector'),
        cell=analysis.get('cell'),
        village=analysis.get('village'),
        summary=analysis.get('summary', ''),
        recommended_action=analysis.get('recommended_action', ''),
        priority_score=analysis.get('priority_score', 0),
        confidence=analysis.get('confidence', 0),
        department=analysis.get('department'),
        estimated_resolution=analysis.get('estimated_resolution'),
        estimated_people_affected=analysis.get('estimated_people_affected', 0),
        public_safety_risk=analysis.get('public_safety_risk', 'Low'),
        economic_impact=analysis.get('economic_impact', 'Low'),
        environmental_impact=analysis.get('environmental_impact', 'Low'),
        urgency=analysis.get('urgency', 'Routine'),
        duplicate_detected=analysis.get('duplicate_detected', False),
        similarity_score=analysis.get('similarity_score', 0),
        similar_report_text=analysis.get('similar_report_text'),
        reasoning=analysis.get('reasoning', []),
        ai_insights=analysis.get('ai_insights', []),
        keywords=analysis.get('keywords', []),
    )

    result = report_to_dict(report)
    if duplicate:
        result['duplicate_warning'] = {
            'id': duplicate.id,
            'summary': duplicate.summary,
            'status': duplicate.status,
        }

    return Response(result, status=status.HTTP_201_CREATED)


# ── /api/reports/<id>/status/ ──────────────────────────────────────────
@api_view(['PATCH'])
def update_status(request, pk):
    try:
        report = Report.objects.get(pk=pk)
    except Report.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    valid = [s[0] for s in Report.STATUS_CHOICES]
    if new_status not in valid:
        return Response({'error': f'status must be one of {valid}'}, status=status.HTTP_400_BAD_REQUEST)

    report.status = new_status
    report.save()
    return Response(report_to_dict(report))


# ── /api/dashboard/ ────────────────────────────────────────────────────
@api_view(['GET'])
def dashboard(request):
    all_reports = Report.objects.all()
    # Sort by AI priority_score now, not just severity bucket
    sorted_reports = sorted(all_reports, key=lambda r: -r.priority_score)

    return Response({
        'total': all_reports.count(),
        'high': all_reports.filter(severity__in=['Critical', 'High']).count(),
        'medium': all_reports.filter(severity='Medium').count(),
        'low': all_reports.filter(severity='Low').count(),
        'open': all_reports.filter(status='open').count(),
        'in_progress': all_reports.filter(status='in_progress').count(),
        'resolved': all_reports.filter(status='resolved').count(),
        'priority_list': [report_to_dict(r) for r in sorted_reports],
    })


# ── /api/reports/<id>/export/ ─────────────────────────────────────────
@api_view(['GET'])
def export_pdf(request, pk):
    try:
        report = Report.objects.get(pk=pk)
    except Report.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#e85d04'), spaceAfter=6)
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#888888'), spaceBefore=10)
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#111111'))
    highlight_style = ParagraphStyle('Highlight', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#e85d04'), fontName='Helvetica-Bold')

    SEV_COLOR = {'Critical': '#7c2d12', 'High': '#e53e3e', 'Medium': '#d97706', 'Low': '#16a34a'}
    STATUS_LABEL = {'open': 'Open', 'in_progress': 'In Progress', 'resolved': 'Resolved'}

    story = []

    story.append(Paragraph("CivicPulse AI", title_style))
    story.append(Paragraph("AI Incident Report", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    sev_color = colors.HexColor(SEV_COLOR.get(report.severity, '#888888'))
    meta_data = [
        ['Report ID', f'#{report.id}', 'Category', report.category],
        ['Severity', report.severity, 'Status', STATUS_LABEL.get(report.status, report.status)],
        ['Priority Score', f'{report.priority_score}/100', 'Confidence', f'{report.confidence}%'],
        ['Location', report.location or '—', 'Department', report.department or '—'],
        ['Submitted', report.created_at.strftime('%d %b %Y, %H:%M'), 'Est. Resolution', report.estimated_resolution or '—'],
    ]
    meta_table = Table(meta_data, colWidths=[3*cm, 5.5*cm, 3*cm, 5.5*cm])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f5f5f5')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('TEXTCOLOR', (1, 1), (1, 1), sev_color),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Original Report", label_style))
    story.append(Paragraph(report.text, value_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("AI Summary", label_style))
    story.append(Paragraph(report.summary, value_style))
    story.append(Spacer(1, 0.3*cm))

    if report.reasoning:
        story.append(Paragraph("AI Reasoning", label_style))
        for reason in report.reasoning:
            story.append(Paragraph(f"• {reason}", value_style))
        story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Recommended Action", label_style))
    story.append(Paragraph(report.recommended_action, highlight_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Estimated People Affected", label_style))
    story.append(Paragraph(str(report.estimated_people_affected), value_style))

    doc.build(story)
    buffer.seek(0)

    filename = f"civicpulse_ai_incident_report_{report.id}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response