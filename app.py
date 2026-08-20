{% extends "base.html" %}

{% block title %}الرئيسية{% endblock %}
{% block page_title %}نظرة عامة{% endblock %}

{% block content %}
<div class="fade-in">

  <!-- Flash Messages -->
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show mb-3" role="alert">
          {{ message }}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <!-- Quick Key Generation Section -->
  <div class="card bg-dark text-white border-secondary mb-4">
    <div class="card-body">
      <h5 class="card-title mb-3">➕ توليد مفتاح جديد (Generate Key Code)</h5>
      <form method="POST" action="/dashboard" class="row g-2 align-items-center">
        <div class="col-auto">
          <select name="key_type" class="form-select bg-secondary text-white border-0">
            <option value="basic">عادي (Basic)</option>
            <option value="premium">مميز (Premium)</option>
            <option value="vip">VIP</option>
          </select>
        </div>
        <div class="col-auto">
          <button type="submit" class="btn btn-success fw-bold">
            إنشاء Key Code
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- Stats Cards -->
  <div class="row g-3 mb-4">
    <div class="col-md-3 col-6">
      <div class="stat-card text-center p-3 bg-dark border border-secondary rounded">
        <div class="stat-number h3 text-primary">{{ total_keys }}</div>
        <div class="stat-label text-muted">إجمالي المفاتيح</div>
      </div>
    </div>
    <div class="col-md-3 col-6">
      <div class="stat-card text-center p-3 bg-dark border border-secondary rounded">
        <div class="stat-number h3 text-warning">{{ used_keys }}</div>
        <div class="stat-label text-muted">مفعلة</div>
      </div>
    </div>
    <div class="col-md-3 col-6">
      <div class="stat-card text-center p-3 bg-dark border border-secondary rounded">
        <div class="stat-number h3 text-success">{{ available_keys }}</div>
        <div class="stat-label text-muted">متاحة</div>
      </div>
    </div>
    <div class="col-md-3 col-6">
      <div class="stat-card text-center p-3 bg-dark border border-secondary rounded">
        <div class="stat-number h3 text-info">
          {% if total_keys > 0 %}
            {{ ((used_keys / total_keys * 100)|round|int) }}%
          {% else %}
            0%
          {% endif %}
        </div>
        <div class="stat-label text-muted">نسبة التفعيل</div>
      </div>
    </div>
  </div>

  <!-- Keys Table -->
  <div class="card-custom bg-dark border border-secondary rounded p-3 text-white">
    <div class="card-header fw-bold mb-3 border-bottom border-secondary pb-2">
      <i class="fa fa-history"></i> آخر المفاتيح
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-dark table-hover mb-0 text-center">
          <thead>
            <tr>
              <th>المفتاح</th>
              <th>النوع</th>
              <th>الاستخدام</th>
              <th>مستخدم</th>
              <th>الإجراءات</th>
            </tr>
          </thead>
          <tbody>
            {% for key in recent_keys %}
            <tr>
              <td><code>{{ key.key }}</code></td>
              <td>
                {% if key.key_type == 'vip' %}
                  <span class="badge bg-danger">VIP</span>
                {% elif key.key_type == 'premium' %}
                  <span class="badge bg-warning text-dark">مميز</span>
                {% else %}
                  <span class="badge bg-secondary">عادي</span>
                {% endif %}
              </td>
              <td>
                {% if key.status == 'active' %}
                  <span class="badge bg-success">نشط / متاح</span>
                {% else %}
                  <span class="badge bg-danger">مستعمل</span>
                {% endif %}
              </td>
              <td>{{ key.used_by }}</td>
              <td>
                <a href="/delete/{{ key.id }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('هل أنت تأكد من الحذف؟')">حذف</a>
              </td>
            </tr>
            {% else %}
            <tr>
              <td colspan="5" class="text-muted py-3">لا توجد مفاتيح مستخدمة أو مضافة. استخدم الخيار أعلى الصفحة لتوليد مفتاح.</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

</div>
{% endblock %}