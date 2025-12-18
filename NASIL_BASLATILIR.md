# AÖF Soru İptal Aracı - Kurulum ve Başlangıç

Bu proje, Python ve FastAPI kullanarak PDF üzerindeki soruları iptal etmenizi sağlayan bir web aracıdır.

## Gereksinimler

- Python 3.7 veya üzeri

## Kurulum

Gerekli kütüphaneleri yüklemek için terminalde proje dizininde şu komutu çalıştırın:

```bash
pip install fastapi uvicorn pymupdf python-multipart
```


## Hızlı Başlatma (Masaüstü Uygulaması Gibi)

Projenin içindeki `baslat.command` dosyasına çift tıklayarak uygulamayı kolayca açabilirsiniz.
Bu dosya otomatik olarak terminali açar, sunucuyu başlatır ve tarayıcınızı `http://127.0.0.1:8000` adresine yönlendirir.

Eğer dosya açılmıyorsa (yetki hatası), terminalde şu komutu bir kez çalıştırın:
```bash
chmod +x baslat.command
```

## Manuel Başlatma (Terminalden)
1. Terminalde proje klasörüne gidin:
   ```bash
   cd /path/to/project
   ```
2. Sunucuyu başlatın:
   ```bash
   uvicorn server:app --reload
   ```
3. Tarayıcıda `http://127.0.0.1:8000` adresine gidin.
2. "PDF Seç" butonuna tıklayarak işlem yapmak istediğiniz PDF dosyasını yükleyin.
3. "İptal edilen sorular" kutusuna iptal edilecek soru numaralarını virgülle ayırarak girin (örn: 3, 5, 12).
4. "Uygula ve PDF Oluştur" butonuna tıklayın.
5. İşlem tamamlandığında "İptalli PDF’i indir" linki belirecektir.
