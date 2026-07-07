from django.db import models


class Report(models.Model):
    SEVERITY_CHOICES = [
        ('Critical', 'Critical'),
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    ]
    CATEGORY_CHOICES = [
        ('Infrastructure', 'Infrastructure'),
        ('Safety', 'Safety'),
        ('Utilities', 'Utilities'),
        ('Environment', 'Environment'),
        ('Health', 'Health'),
        ('Transport', 'Transport'),
        ('Education', 'Education'),
        ('Security', 'Security'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    ]
    URGENCY_CHOICES = [
        ('Immediate', 'Immediate'),
        ('Within 24 Hours', 'Within 24 Hours'),
        ('Within 3 Days', 'Within 3 Days'),
        ('Routine', 'Routine'),
    ]
    IMPACT_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    text = models.TextField()
    title = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Infrastructure')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='Low')
    location = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    sector = models.CharField(max_length=100, blank=True, null=True)
    cell = models.CharField(max_length=100, blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    summary = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    # ── New AI-derived fields ──
    priority_score = models.IntegerField(default=0)
    confidence = models.IntegerField(default=0)
    department = models.CharField(max_length=100, blank=True, null=True)
    estimated_resolution = models.CharField(max_length=100, blank=True, null=True)
    estimated_people_affected = models.IntegerField(default=0)
    public_safety_risk = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='Low')
    economic_impact = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='Low')
    environmental_impact = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='Low')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='Routine')
    duplicate_detected = models.BooleanField(default=False)
    similarity_score = models.IntegerField(default=0)
    similar_report_text = models.TextField(blank=True, null=True)
    reasoning = models.JSONField(default=list, blank=True)
    ai_insights = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.severity}] {self.category} - {self.text[:50]}'