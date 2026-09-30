from django import forms
from django.forms import formset_factory

from apps.kawasan.models import Kawasan

from .constants import Status
from .parser import assign_lat_lon, in_indonesia

INPUT = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-forest-600 focus:ring-2 focus:ring-forest-100"


class LaporanForm(forms.Form):
    tanggal = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": INPUT}, format="%Y-%m-%d"))
    kawasan = forms.ModelChoiceField(Kawasan.objects.all(), empty_label="— pilih kawasan —")
    upaya = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4, "class": INPUT}))
    rencana = forms.CharField(label="Rencana tindak lanjut", required=False,
                              widget=forms.Textarea(attrs={"rows": 4, "class": INPUT}))
    personel = forms.CharField(label="Jumlah personel", required=False, max_length=500,
                               widget=forms.TextInput(attrs={"class": INPUT}))
    kendala = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": INPUT}))
    kebutuhan = forms.CharField(label="Kebutuhan / saran", required=False,
                                widget=forms.Textarea(attrs={"rows": 2, "class": INPUT}))
    gakkum = forms.CharField(label="Penegakan hukum (Gakkum)", required=False,
                             widget=forms.Textarea(attrs={"rows": 2, "class": INPUT}))
    laporan = forms.CharField(label="Narasi laporan lengkap", required=False,
                              widget=forms.Textarea(attrs={"rows": 6, "class": INPUT}))

    def clean(self):
        data = super().clean()
        for k in ("upaya", "rencana", "personel", "kendala", "kebutuhan", "gakkum", "laporan"):
            if k in data:
                data[k] = data[k].strip()
        return data


class PointForm(forms.Form):
    lat = forms.FloatField(label="Lintang", widget=forms.NumberInput(attrs={"step": "any", "class": INPUT, "placeholder": "-2.321"}))
    lon = forms.FloatField(label="Bujur", widget=forms.NumberInput(attrs={"step": "any", "class": INPUT, "placeholder": "113.921"}))
    status = forms.ChoiceField(choices=Status.choices, initial=Status.UPAYA, widget=forms.Select(attrs={"class": INPUT}))
    luas = forms.DecimalField(label="Luas (ha)", min_value=0, decimal_places=2, max_digits=12, initial=0,
                              widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": INPUT}))

    def clean(self):
        data = super().clean()
        lat, lon = data.get("lat"), data.get("lon")
        if lat is None or lon is None:
            return data
        if not in_indonesia(lat, lon):
            if assign_lat_lon(lat, lon):
                raise forms.ValidationError("Lintang dan bujur tampak tertukar. Lintang Indonesia berkisar -11 s/d 6, bujur 95 s/d 141.")
            raise forms.ValidationError("Koordinat berada di luar wilayah Indonesia. Periksa kembali lintang dan bujur.")
        return data


PointFormSet = formset_factory(PointForm, extra=0, min_num=1, validate_min=True)
