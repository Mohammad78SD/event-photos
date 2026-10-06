from django import forms

from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "names_latin",
            "event_at",
            "cover_image",
            "welcome_text",
            "is_open",
            "gallery_shared",
            "require_approval",
            "max_file_mb",
            "max_files_batch",
            "quota_gb",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "field-input", "placeholder": "عقد و نامزدی سارا و علی"}),
            "names_latin": forms.TextInput(attrs={"class": "field-input", "placeholder": "Sara|Ali"}),
            "event_at": forms.DateTimeInput(attrs={"class": "field-input", "type": "datetime-local"}),
            "cover_image": forms.FileInput(attrs={"class": "field-input"}),
            "welcome_text": forms.Textarea(attrs={"class": "field-input h-24 py-3", "rows": 4}),
            "is_open": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
            "gallery_shared": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
            "require_approval": forms.CheckboxInput(attrs={"class": "peer sr-only"}),
            "max_file_mb": forms.NumberInput(attrs={"class": "field-input"}),
            "max_files_batch": forms.NumberInput(attrs={"class": "field-input"}),
            "quota_gb": forms.NumberInput(attrs={"class": "field-input"}),
        }
        labels = {
            "title": "عنوان مراسم",
            "names_latin": "نام‌های عروس و داماد (به اینگلیسی، جدا شده با |)",
            "event_at": "تاریخ و ساعت مراسم",
            "cover_image": "عکس روی صفحه",
            "welcome_text": "متن خوش‌آمدگویی",
            "is_open": "مراسم باز است برای دریافت عکس",
            "gallery_shared": "گالری برای مهمان‌ها قابل نمایش است",
            "require_approval": "عکس‌ها نیاز به تأیید دارند",
            "max_file_mb": "حداکثر اندازه هر عکس (مگابایت)",
            "max_files_batch": "حداکثر تعداد عکس در یک بار ارسال",
            "quota_gb": "کل سقف ذخیره‌سازی (گیگابایت)",
        }
