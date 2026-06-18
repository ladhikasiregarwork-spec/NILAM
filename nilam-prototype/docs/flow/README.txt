==========================================================================
 NILAM PROTOTYPE - DOKUMENTASI FLOW (Bahasa Indonesia)
==========================================================================

Folder ini berisi penjelasan alur (flow) per langkah dari aplikasi NILAM,
termasuk integrasi OCR untuk Slip Gaji dan SK Perusahaan.

Daftar dokumen:

  01-flow-mobile.txt        Alur aplikasi mobile (sisi nasabah), per step.
  02-flow-ocr-integrasi.txt Alur integrasi OCR slip gaji & SK (detail).
  03-flow-dashboard.txt     Alur dashboard menampilkan tiap section.
  04-cara-menjalankan.txt   Cara menjalankan service OCR + aplikasi (runbook).
  05-flow-upload-classifier.txt  ALUR TERBARU: satu menu upload + classifier
                                 (menggantikan langkah upload di 01).

Ringkasan singkat:

  - Mobile: Masuk -> Upload Dokumen (5 dokumen, satu per satu) ->
            Identifikasi (processing) -> Menunggu Feedback.
  - 2 dokumen dibaca OCR ASLI dari PDF di komputer:
        * Slip Gaji      -> service slip-gaji-ocr      (port 8012)
        * SK Perusahaan  -> service keterangan-kerja-ocr (port 8011)
  - 3 dokumen lain (KTP, KK, Bank Statement) masih SIMULASI (data contoh).
  - Hasil OCR ditampilkan di kartu dashboard "Salary Slip" dan "SK Perusahaan".

Mode saat ini: RULE-BASED (tanpa LLM). Kredensial LLM belum dipakai.
==========================================================================
