# 🚀 HƯỚNG DẪN ĐẦY ĐỦ — ĐƯA WEB LÊN INTERNET MIỄN PHÍ 100%

> **Đây là tài liệu duy nhất bạn cần.** Mở file này ra và làm lần lượt từ trên xuống.
> Mọi thứ đã được kiểm tra thực tế: RAM app, cú pháp script, giới hạn của từng nhà cung cấp.

---

## 📌 MỤC LỤC

- [PHẦN 0 — Chọn hướng đi: Render hay Oracle?](#phần-0--chọn-hướng-đi)
- [GIAI ĐOẠN 1 — ĐƯA WEB LÊN MẠNG NGAY HÔM NAY (7 việc, ~60 phút)](#giai-đoạn-1--đưa-web-lên-mạng-ngay-hôm-nay)
  - [VIỆC 1 — Đổi key Gemini](#việc-1--đổi-key-gemini)
  - [VIỆC 2 — Đẩy code lên GitHub](#việc-2--đẩy-code-lên-github)
  - [VIỆC 3 — Deploy lên Render](#việc-3--deploy-lên-render)
  - [VIỆC 4 — Bật bảo vệ dữ liệu Supabase](#việc-4--bật-bảo-vệ-dữ-liệu-supabase)
  - [VIỆC 5 — Chống Supabase tự pause](#việc-5--chống-supabase-tự-pause)
  - [VIỆC 6 — Chống Render "ngủ đông"](#việc-6--chống-render-ngủ-đông-nên-làm)
  - [VIỆC 7 — Kiểm tra tổng thể](#việc-7--kiểm-tra-tổng-thể)
- [GIAI ĐOẠN 2 (tùy chọn sau này) — Nâng cấp lên Oracle 24/7](#giai-đoạn-2-tùy-chọn--nâng-cấp-lên-oracle-cloud-247)
- [Cập nhật web về sau](#-cập-nhật-web-về-sau)
- [Xử lý sự cố](#-xử-lý-sự-cố)
- [Câu hỏi thường gặp](#-câu-hỏi-thường-gặp)
- [Checklist cuối cùng](#-checklist-cuối-cùng)

---

# PHẦN 0 — CHỌN HƯỚNG ĐI

## Bảng so sánh thật (đã kiểm tra ngày hôm nay)

| | **Render Free** ✅ khuyên dùng | **Oracle Always Free** (để sau) |
|---|---|---|
| Có gói miễn phí? | ✅ Có | ✅ Có, vĩnh viễn |
| Cần thẻ tín dụng? | ❌ **KHÔNG CẦN** | ⚠️ **BẮT BUỘC** (thẻ VN hay bị từ chối) |
| Thời gian deploy | **15 phút** | 45+ phút |
| Cách làm | Bấm nút trên web | Gõ lệnh SSH |
| HTTPS (ổ khoá 🔒) | ✅ **Tự động có sẵn** | ⚠️ Phải tự cài thêm |
| Cấu hình | 0.1 CPU / 512 MB | 4 CPU / 24 GB |
| Chạy 24/7? | ⚠️ Ngủ sau 15 phút không ai truy cập | ✅ Thức 24/7 |
| Thời gian "thức dậy" | ~1 phút | 0 giây |
| **Có chạy được app này không?** | ✅ **Thoải mái** (app chỉ dùng **53 MB RAM**) | ✅ Quá dư |

## Kết luận về Koyeb (vì bạn có hỏi)

> ❌ **Koyeb đã bỏ gói miễn phí.** Tôi vừa vào trang giá của Koyeb kiểm tra: giờ chỉ còn
> **Pro $29/tháng**, **Scale $299/tháng** và Enterprise. Không còn gói $0 nào.
> Vậy nên lời khuyên "dùng Koyeb trước" bạn đọc được là **thông tin cũ** (Koyeb bỏ free tier
> từ 2025, sau khi Hugging Face cũng bỏ Docker Space miễn phí).

## Vậy hướng đi đúng là gì?

```
   HÔM NAY  ──▶  Render Free  ──▶  Web chạy trên internet, có HTTPS,
              (không cần thẻ)      bạn dùng được ngay, học viên vào được ngay

   SAU NÀY  ──▶  Oracle Cloud  ──▶  Nâng cấp lên 24/7, nhanh hơn (tùy chọn)
                (cần thẻ)
```

**Quan trọng:** hai giai đoạn này **độc lập nhau**. Bạn làm Render xong là web sống.
Oracle là "phần thưởng" về sau, không ảnh hưởng gì tới Render.

### Còn Netlify thì sao?

Netlify **chỉ host được file tĩnh** (HTML/CSS/JS). App của bạn có Python
(FastAPI + Tesseract OCR + spaCy) → **không thể** chạy trên Netlify.
Hiện tại `index.html` đã được backend Python phục vụ luôn, nên bạn **không cần Netlify**.

---

# GIAI ĐOẠN 1 — ĐƯA WEB LÊN MẠNG NGAY HÔM NAY

**Tổng thời gian: ~60 phút. Không cần thẻ. Không cần biết Linux.**

| # | Việc | Thời gian |
|---|---|---|
| 1 | Đổi key Gemini | 10 phút |
| 2 | Đẩy code lên GitHub | 15 phút |
| 3 | Deploy lên Render | 15 phút |
| 4 | Bật bảo vệ dữ liệu Supabase | 10 phút |
| 5 | Chống Supabase tự pause | 5 phút |
| 6 | Chống Render "ngủ đông" (nên làm) | 10 phút |
| 7 | Kiểm tra tổng thể | 10 phút |

---

## VIỆC 1 — 🔑 ĐỔI KEY GEMINI

### Chuyện gì đang xảy ra?

**API key Gemini** giống như **mật khẩu** để app gọi AI của Google. Ai có key này thì dùng
AI "miễn phí trên tài khoản của bạn".

Hiện key đang được **viết cứng trong 2 file code**:
- `python_backend/main.py` (dòng 575)
- `python_backend/prefill_ho_tu_gemini.py` (dòng 39)

Khi đẩy code lên GitHub, **cả thế giới đọc được** → coi như key đã bị lộ. Và điều quan
trọng nhất:

> ⚠️ **Xoá key trong code cũng không cứu được**, vì nó nằm vĩnh viễn trong **lịch sử Git**
> của repo. Nên bắt buộc phải **XOÁ (REVOKE) key cũ** trên Google.

### Các bước

**Bước 1 — Tạo key mới**

1. Mở https://aistudio.google.com/apikey
2. Đăng nhập Google → bấm **Create API key** → chọn project → **Create**
3. **Copy key mới**, dán tạm vào Notes

**Bước 2 — Xoá key cũ (BẮT BUỘC, đừng bỏ qua)**

1. Vẫn ở https://aistudio.google.com/apikey
2. Tìm key **cũ** (bắt đầu bằng `AQ.Ab8RN6...`) → bấm **⋮ / Delete** → xác nhận
3. Từ giây phút này key cũ trong code đã **vô dụng**

**Bước 3 — Lưu key mới vào máy bạn**

```bash
cd "web học/python_backend"
echo "GEMINI_API_KEY=key_moi_vua_copy" > .env
```

> File `.env` đã được `.gitignore` chặn → **không bao giờ bị đẩy lên GitHub** (tôi đã
> kiểm tra và xác nhận an toàn ✅).

### ✅ Xong VIỆC 1 khi: có key mới trong Notes + đã xoá key cũ trên Google.

---

## VIỆC 2 — 📤 ĐẨY CODE LÊN GITHUB

### 2.1. Tạo tài khoản GitHub

https://github.com/signup → điền email, mật khẩu, tên đăng nhập → xác nhận email.
Miễn phí, **không cần thẻ**.

### 2.2. Đẩy code lên

**Cách A — GitHub CLI (2 lệnh):**

```bash
cd "web học"
gh auth login                      # chọn GitHub.com → HTTPS → login qua trình duyệt
gh repo create app-luyen-doc --public --source=. --remote=origin --push
```

**Cách B — Làm bằng trình duyệt:**

1. Mở https://github.com/new
   - **Repository name**: `app-luyen-doc`
   - Chọn **Public** ← bắt buộc (Render gói free đọc code công khai)
   - ⚠️ **KHÔNG** tích "Add a README", "Add .gitignore", "Choose a license"
   - Bấm **Create repository**
2. Chạy trên máy bạn:

```bash
cd "web học"
git remote add origin https://github.com/TEN-GITHUB-CUA-BAN/app-luyen-doc.git
git branch -M main
git push -u origin main
```

3. Khi được hỏi **Password**, đừng nhập mật khẩu GitHub (GitHub đã bỏ cách này).
   Phải dùng **Personal Access Token**:
   - Mở https://github.com/settings/tokens → **Generate new token (classic)**
   - Note: `deploy` — Expiration: 90 days
   - Tích ô **repo** → **Generate token** → copy chuỗi `ghp_...`
   - Dán chuỗi đó vào chỗ hỏi Password

### 2.3. Kiểm tra sống còn

```bash
cd "web học"
git status                          # phải ghi "nothing to commit, working tree clean"
git ls-files | grep "\.env$"        # KHÔNG được in ra gì cả
```

→ Nếu lệnh thứ 2 **không in gì** = an toàn ✅ (nếu có in `.env` thì báo tôi ngay).

### ✅ Xong VIỆC 2 khi: mở `https://github.com/TEN-BAN/app-luyen-doc` thấy đủ code.

---

## VIỆC 3 — ☁️ DEPLOY LÊN RENDER (phần chính!)

### 3.1. Tạo tài khoản Render

1. Mở https://dashboard.render.com/register
2. Bấm **GitHub** để đăng ký bằng tài khoản GitHub (nhanh nhất) → **Authorize Render**
3. **Không cần nhập thẻ** ✅

### 3.2. Tạo Web Service

1. Trong Dashboard, bấm nút **New +** (góc trên phải) → chọn **Web Service**
2. Chọn **Build and deploy from a Git repository** → **Next**
3. Bấm **Connect** cạnh repo `app-luyen-doc`
   *(Nếu không thấy repo: bấm "Configure account" và cấp quyền cho Render đọc repo đó)*
4. Điền form như sau:

| Mục | Điền gì |
|---|---|
| **Name** | `app-luyen-doc` → link sẽ là `https://app-luyen-doc.onrender.com` |
| **Region** | **Singapore** (gần Việt Nam nhất) |
| **Branch** | `main` |
| **Language / Runtime** | **Docker** *(Render tự nhận ra vì đã có `Dockerfile`)* |
| **Instance Type** | **Free** (0$/tháng) |

5. Kéo xuống mục **Environment Variables** → bấm **Add Environment Variable**, thêm 2 dòng:

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | *(dán key Gemini mới của bạn vào đây)* |
| `ALLOWED_ORIGINS` | `*` |

6. (Tùy chọn) Mở **Advanced** → **Health Check Path**: `/cn/tra-tu/%E5%AD%A6`
7. Bấm **Create Web Service** → Render bắt đầu build

### 3.3. Đợi build (~5-10 phút)

Bạn sẽ thấy log chạy liên tục. Đợi đến khi dòng trạng thái đổi thành **Live** (màu xanh).

> ⚠️ **Lưu ý về tên:** nếu `app-luyen-doc` đã bị người khác dùng, Render sẽ báo.
> Lúc đó đổi thành ví dụ `app-luyen-doc-cua-ban` và ghi nhớ link mới.

**Link web của bạn:** `https://app-luyen-doc.onrender.com` 🔒 (có HTTPS tự động)

### 3.4. Cách B — Deploy nhanh hơn bằng Blueprint (nếu muốn)

Repo đã có sẵn file `render.yaml` chứa toàn bộ cấu hình đúng:
**New +** → **Blueprint** → chọn repo → Render tự đọc `render.yaml` → hỏi bạn
`GEMINI_API_KEY` → dán vào → **Apply**. Render tự làm hết phần còn lại.

### 3.5. ⚠️ Những điều PHẢI biết về gói Free của Render

| Điều gì | Chi tiết | Bạn phải làm gì |
|---|---|---|
| **Ngủ sau 15 phút** | Không ai truy cập 15 phút → Render cho app "ngủ". Lần vào sau đợi ~1 phút | Xem **VIỆC 6** để chống |
| **750 giờ/tháng** | Mỗi workspace được 750 giờ máy chủ/tháng. Vượt → **tạm dừng hết** dịch vụ free tới đầu tháng sau | Đừng bật 24/7 vô tội vạ (VIỆC 6 có cách tính an toàn) |
| **Ổ cứng tạm thời** | File người dùng upload sẽ **mất** khi app restart | ✅ Không sao — dữ liệu thật của bạn nằm trên **Supabase** |
| **Build chậm** | Mỗi lần push code = 1 lần build 5-10 phút | Đừng push quá nhiều lần trong ngày |
| **Không có SSH** | Gói free không cho vào shell | Muốn xem lỗi thì xem tab **Logs** |

### ✅ Xong VIỆC 3 khi: dòng trạng thái là **Live** và mở link Render thấy web hiện ra.

---

## VIỆC 4 — 🛡️ BẬT BẢO VỆ DỮ LIỆU SUPABASE

### Vì sao phải làm? (rất quan trọng)

Trong `index.html` có đoạn sửa/xoá bài viết:

```js
await supabaseClient.from('articles').update({ title: newTitle }).eq('id', articleId);
await supabaseClient.from('articles').delete().eq('id', id);
```

👉 Chú ý: **chỉ lọc theo `id`, KHÔNG lọc theo người dùng.**

Nếu Supabase **chưa bật RLS** (bảo vệ theo từng dòng), thì bất kỳ ai mở web của bạn cũng
lấy được **anon key** (key này nằm công khai trong `index.html` — đó là thiết kế bình
thường của Supabase), rồi có thể **sửa/xoá bài viết của mọi người**.

**RLS** = quy tắc ở tầng database: *"mỗi người chỉ được đọc/ghi dòng dữ liệu của chính mình"*.

### Chạy SQL

1. Vào https://supabase.com/dashboard → chọn project của bạn
2. Menu trái → **SQL Editor** → **New query**
3. Dán toàn bộ đoạn dưới → bấm **Run**

```sql
-- ============================================================
-- BẬT BẢO VỆ: mỗi người chỉ thao tác được trên bài viết của mình
-- ============================================================

-- 1) Bật RLS cho bảng articles
alter table public.articles enable row level security;

-- 2) Xoá policy cũ (nếu có) để tránh trùng khi chạy lại
drop policy if exists "Users can view own articles"   on public.articles;
drop policy if exists "Users can insert own articles" on public.articles;
drop policy if exists "Users can update own articles" on public.articles;
drop policy if exists "Users can delete own articles" on public.articles;

-- 3) Tạo 4 quy tắc: XEM - THÊM - SỬA - XOÁ (chỉ trên bài của mình)
create policy "Users can view own articles"
  on public.articles for select
  using (auth.uid() = user_id);

create policy "Users can insert own articles"
  on public.articles for insert
  with check (auth.uid() = user_id);

create policy "Users can update own articles"
  on public.articles for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can delete own articles"
  on public.articles for delete
  using (auth.uid() = user_id);
```

4. Kết quả đúng: **"Success. No rows returned"** ✅
5. Kiểm tra: menu trái → **Table Editor** → bảng `articles` → thấy **RLS enabled** 🔒

**Nếu báo lỗi** `column "user_id" does not exist`: chụp màn hình Table Editor gửi tôi,
tôi sửa lại SQL (nghĩa là cột trong bảng bạn đặt tên khác).

### Khai báo địa chỉ web cho Supabase

1. Supabase → **Authentication** → **URL Configuration**
2. **Site URL**: `https://app-luyen-doc.onrender.com`
3. **Redirect URLs** → **Add URL** → dán y hệt
4. **Save**

> Để khi người dùng đăng nhập / xác nhận email, Supabase biết chuyển họ về đúng web của bạn.

### ✅ Xong VIỆC 4 khi: SQL chạy thành công + bảng articles có RLS 🔒.

---

## VIỆC 5 — 😴 CHỐNG SUPABASE TỰ "PAUSE"

### Vì sao Supabase pause?

Supabase cho database miễn phí, nhưng để tiết kiệm tài nguyên họ **tự tạm dừng** project nào
**7 ngày liên tục không có hoạt động API** — đó là email bạn đã nhận.

**Bị pause thì sao?**
- ❌ Web vẫn mở, nhưng **đăng nhập / lưu bài sẽ lỗi** (database ngủ rồi)
- ✅ **Dữ liệu KHÔNG mất**
- 🔧 Khôi phục: vào dashboard → chọn project → **Restore project**

👉 Không nguy hiểm, chỉ phiền. Cách chữa rất đơn giản:

### Cách chống: robot "điểm danh" mỗi 2 ngày

Dùng **GitHub Actions** (miễn phí) tạo robot tự gọi 1 truy vấn rất nhẹ vào Supabase mỗi
2 ngày. Có request = có hoạt động = **không bao giờ bị pause**.

Tôi đã tạo sẵn file **`.github/workflows/giu-supabase-thuc.yml`** (đã kiểm tra cú pháp ✅).

### Bật lên

Nếu bạn đã đẩy code lên ở VIỆC 2 thì **đã xong rồi** — file này nằm sẵn trong repo.
Kiểm tra: mở `https://github.com/TEN-BAN/app-luyen-doc/actions`
→ phải thấy workflow tên **"Giu Supabase hoat dong"**.

**Chạy thử ngay** (không cần đợi 2 ngày): bấm vào workflow → **Run workflow** →
**Run workflow** → đợi ~20 giây → Refresh → thấy ✅ xanh là tốt.

### ⚠️ Cái bẫy GitHub mà tôi đã xử lý sẵn

GitHub có luật ít người biết: **workflow theo lịch bị TẮT TỰ ĐỘNG nếu repo 60 ngày không
có commit nào**. Nghĩa là bạn không sửa code 2 tháng → robot âm thầm chết → Supabase bị pause.

→ File tôi viết đã **tự xử lý**: cứ 45 ngày nó tự tạo 1 commit
`"Gia han lich diem danh Supabase"` để repo luôn "thức".

> Vì vậy bạn sẽ thấy thỉnh thoảng có commit tên **github-actions[bot]** — **bình thường**,
> đừng xoá.

### ✅ Xong VIỆC 5 khi: tab Actions có workflow chạy xanh.

---

## VIỆC 6 — ⏰ CHỐNG RENDER "NGỦ ĐÔNG" (nên làm)

### Vấn đề

Render Free cho app **ngủ sau 15 phút** không có ai truy cập. Lần vào sau phải đợi **~1 phút**.
Học viên vào buổi sáng sẽ gặp màn hình "đang khởi động".

### Cách chữa: robot GitHub tự "gõ cửa" web (ĐÃ LÀM SẴN ✅)

Tôi đã tạo sẵn file **`.github/workflows/giu-web-thuc.yml`** — một robot **miễn phí** chạy
ngay trên GitHub, tự mở web của bạn **mỗi 5 phút**, trong khoảng **06:00 → 23:00 giờ Việt Nam**.

**Việc bạn cần làm: KHÔNG CẦN LÀM GÌ CẢ** 🎉 — chỉ cần file nằm trên GitHub là nó tự chạy.

**Muốn xem nó có chạy không?**
Mở `https://github.com/TEN-BAN/app-luyen-doc/actions` → thấy workflow **"Giu web Render thuc"**
→ bấm **Run workflow** → **Run workflow** → đợi ~1 phút → thấy ✅ xanh là tốt.

> 🤖 Robot này chỉ mở **trang chủ** (file tĩnh) nên cực nhẹ, **không tốn tiền Gemini**
> và không làm chậm web.

**Nếu muốn thêm 1 lớp dự phòng** (tùy chọn, không bắt buộc) thì dùng cron-job.org:

1. Đăng ký: https://cron-job.org/en/signup/ (chỉ cần email)
2. Vào **Cronjobs** → **Create cronjob**
3. Điền:

| Mục | Điền gì |
|---|---|
| **Title** | `Giu web thuc` |
| **URL** | `https://app-luyen-doc.onrender.com/` |
| **Schedule** | chọn **Custom** (tùy chỉnh) — dòng **cuối cùng** trong danh sách |
| **Cron expression** | `*/5 6-23 * * *` |
| **Time zone** | `Asia/Ho_Chi_Minh` |

4. **Save** → bấm **TEST RUN** để chạy thử ngay

> ⚠️ **Lưu ý quan trọng:** bản cron-job.org hiện tại **đã bỏ bảng tích chọn giờ** (bản cũ có).
> Nếu bạn không thấy ô **Custom** / **Cron expression** thì cứ **bỏ qua bước này** —
> robot GitHub ở trên đã lo được việc giữ web thức rồi.
>
> `*/5 6-23 * * *` đọc là: *"cứ 5 phút một lần, chỉ trong khoảng 6 giờ sáng → 11 giờ đêm"*.

### ⚠️ Bài toán "750 giờ" — PHẢI hiểu để không bị tạm dừng

Render cho **750 giờ/tháng**. Nếu bạn cho app chạy 24/7:

```
24 giờ × 31 ngày = 744 giờ  →  chỉ còn 6 giờ dự phòng  ⚠️ QUÁ NGUY HIỂM
```

Vì vậy ta chỉ giữ app thức trong **giờ học**:

```
17 giờ/ngày (06:00–23:00) × 31 ngày = 527 giờ  →  an toàn, còn dư 223 giờ  ✅
```

**Kết quả:** từ 6 giờ sáng đến 11 giờ đêm, học viên vào là có kết quả **ngay lập tức**.
Chỉ buổi đêm (0h–6h) mới phải chờ ~1 phút — điều này hoàn toàn chấp nhận được.

> 💡 Nếu bạn hay học khuya, có thể đổi thành 05:00–24:00 = 19 giờ/ngày = 589 giờ ✅ vẫn an toàn.
> **Tuyệt đối đừng** chọn 24/7.

### ✅ Xong VIỆC 6 khi: tab Actions có workflow **"Giu web Render thuc"** chạy xanh,
và mở web vào buổi sáng thấy hiện **ngay** (không phải chờ).

---

## VIỆC 7 — ✅ KIỂM TRA TỔNG THỂ

Làm lần lượt 7 bài kiểm tra sau:

| # | Kiểm tra | Kết quả đúng |
|---|---|---|
| 1 | Mở `https://app-luyen-doc.onrender.com` | Hiện trang Tiếng Anh, có 🔒 HTTPS |
| 2 | Bấm nút **中文** | Sang trang Tiếng Trung |
| 3 | Đăng ký tài khoản mới | Nhận email xác nhận (nếu bật) |
| 4 | Đăng nhập → dán đoạn văn → phân tích | Ra danh sách từ vựng (**kiểm tra Gemini key**) |
| 5 | Bấm vào 1 từ | Hiện tooltip giải thích |
| 6 | Upload 1 file PDF/ảnh nhỏ | Trích xuất được chữ (**kiểm tra OCR**) |
| 7 | Lưu 1 bài, F5 tải lại trang | Bài vẫn còn (**kiểm tra RLS hoạt động đúng**) |

**Xem log khi có lỗi:** Render Dashboard → chọn service → tab **Logs**.

> 💡 Trên gói Free (0.1 CPU), upload PDF **lớn** có thể mất 1-2 phút. Nên dùng file
> dưới ~10 trang. Nếu bạn cần xử lý file lớn thường xuyên → xem GIAI ĐOẠN 2.

---

# GIAI ĐOẠN 2 (TÙY CHỌN) — NÂNG CẤP LÊN ORACLE CLOUD 24/7

> ⏭️ **Bạn KHÔNG cần đọc phần này hôm nay.** Chỉ quay lại khi Render đã chạy ổn định
> và bạn muốn web nhanh hơn, không bao giờ ngủ.
> Khi đó nhắn tôi, tôi sẽ đi cùng bạn từng bước.

## Nói thật về Oracle: đâu là "tử huyệt", đâu là tin đồn?

Tôi đã đọc bản phân tích bạn gửi. Nó **đúng về tổng quát**, nhưng **phần lớn các "ải"
nó liệt kê KHÔNG áp dụng cho dự án này**, vì tôi đã viết sẵn script làm hết. Cụ thể:

| "Tử huyệt" được nói | Thực tế với dự án của bạn |
|---|---|
| Phải gõ lệnh Linux, cài Python, copy file | ❌ Không. Tôi đã viết sẵn `oracle/cai-dat-lan-dau.sh` — bạn **dán 3 dòng lệnh là xong**, script tự cài Docker + tải code + build + chạy |
| Phải tự mở port bằng iptables | ❌ Không. Script **tự mở port**; phần VCN bạn chỉ bấm 1 lần trên web |
| **Mixed Content: web https gọi backend http sẽ bị chặn** | ❌ **Không tồn tại trong thiết kế này.** Vì `index.html` được **chính backend phục vụ** (cùng 1 máy chủ, cùng origin `http://IP:8000`). Không có https→http nên trình duyệt không chặn gì cả. Chỉ khi bạn tách frontend sang Netlify mới phát sinh vấn đề này |
| Phải cài Nginx + Certbot để có HTTPS | ❌ Không cần. Nếu muốn HTTPS chỉ cần **1 lệnh Caddy** (tự xin + tự gia hạn chứng chỉ). Và **không bắt buộc**, vì app này không dùng API nào cần HTTPS (không camera, không clipboard, không service worker) |
| Phải học systemd/tmux để chạy ngầm | ❌ Không. Script dùng `docker run -d --restart unless-stopped` → tự chạy ngầm, tự khởi động lại khi reboot, tắt Terminal cũng không sao |

## Còn đây là những "ải" THẬT (tôi không giấu bạn)

| Ải thật | Mức độ | Cách xử lý |
|---|---|---|
| **Thẻ Visa/Mastercard VN bị từ chối** | 🔴 **Đây mới là tử huyệt thật** | Thử: bật "thanh toán quốc tế" trong app ngân hàng; thử thẻ khác; thử visa debit của ngân hàng số (TPBank, MB, VIB...). Không được thì **ở lại Render, vẫn tốt** |
| **"Out of host capacity"** | 🟠 Hay gặp | Đổi Availability Domain (AD-1/2/3), thử giờ khác, hoặc giảm xuống 2 CPU/12 GB |
| Region chọn sai → không sửa được | 🟠 Vừa | Chọn **Singapore** (hoặc Tokyo/Osaka) ngay từ đầu |
| Tài nguyên *Always Free* bị thu hồi nếu "nhàn rỗi" | 🟡 Hiếm | Web có truy cập đều đặn thì không sao |

## Khi nào nên nâng cấp?

- ✅ Khi bạn thường xuyên xử lý PDF/ảnh **lớn** mà Render Free chạy quá chậm
- ✅ Khi bạn muốn web **không bao giờ ngủ** (không phải chờ 1 phút buổi sáng)
- ✅ Khi bạn thấy hứng thú học Linux (lợi ích kèm theo rất lớn cho nghề nghiệp)

## Các file đã chuẩn bị sẵn cho Giai đoạn 2

| File | Công dụng |
|---|---|
| `oracle/cai-dat-lan-dau.sh` | Cài app lên máy ảo bằng **1 lệnh** |
| `oracle/cap-nhat.sh` | Cập nhật web sau khi sửa code |

> Khi bạn sẵn sàng, chỉ cần nhắn: *"Bắt đầu Giai đoạn 2"* — tôi sẽ đưa bạn đi từng bước
> từ đăng ký Oracle → tạo máy ảo → mở port → SSH → chạy script.

---

# 🔄 CẬP NHẬT WEB VỀ SAU

Sửa code trên máy bạn → đẩy lên GitHub → Render **tự động build lại** (không cần làm gì thêm):

```bash
cd "web học"
git add .
git commit -m "Mo ta thay doi"
git push
```

→ Đợi ~5-10 phút (theo dõi ở tab **Logs** trong Render Dashboard).

**Nếu chỉ muốn deploy lại mà không sửa code:** Render Dashboard → **Manual Deploy** → **Deploy latest commit**.

> ⚠️ Mỗi lần build tốn thời gian máy build miễn phí của Render. Đừng push 10 lần/ngày.

**Sau này nếu đã lên Oracle (Giai đoạn 2)** thì cập nhật bằng:
```bash
cd ~/app-luyen-doc && bash oracle/cap-nhat.sh
```

---

# 🧯 XỬ LÝ SỰ CỐ

## Trên Render

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Trang "đang khởi động" 1 phút | App đang ngủ (bình thường với gói Free) | Làm **VIỆC 6** |
| Build báo **Failed** | Lỗi code/thư viện | Mở tab **Logs** → kéo lên tìm dòng `ERROR` → gửi tôi |
| Deploy xong nhưng web báo **502** | App crash khi khởi động | Tab **Logs** → thường do thiếu biến môi trường `GEMINI_API_KEY` |
| Bấm phân tích từ vựng báo lỗi AI | Key Gemini sai/chưa có | Render → **Environment** → sửa `GEMINI_API_KEY` → Save (tự deploy lại) |
| Tooltip không hiện, mọi nút lỗi | Backend chưa lên | Xem Logs, kiểm tra status có phải **Live** không |
| Upload PDF chậm/lỗi | 0.1 CPU + 512 MB | Dùng file nhỏ hơn (<10 trang), hoặc lên Giai đoạn 2 |
| Web bị treo, báo hết hạn mức | **Hết 750 giờ** | Chờ đầu tháng sau, rồi xem lại **VIỆC 6** (robot chỉ chạy 06:00–23:00) |
| Đăng nhập được nhưng không lưu/xoá bài | RLS chưa bật / policy sai | Làm lại **VIỆC 4** |
| Supabase báo "project paused" | Robot điểm danh chưa chạy | Dashboard bấm **Restore**, rồi kiểm tra tab Actions (**VIỆC 5**) |
| Đăng ký xong không thấy email xác nhận | Supabase đang gửi mail giới hạn | Supabase → Authentication → Providers → Email → tắt "Confirm email" để test nhanh |

## Trên Oracle (khi làm Giai đoạn 2)

| Triệu chứng | Cách xử lý |
|---|---|
| Web không mở dù container chạy | `sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT && sudo netfilter-persistent save` |
| Xem log app | `sudo docker logs --tail 100 app-luyen-doc` |
| Kiểm tra app sống | `sudo docker ps` và `curl -I http://127.0.0.1:8000` |
| Sai key Gemini | `nano ~/app-luyen-doc/.env` rồi `bash oracle/cap-nhat.sh` |

---

# ❓ CÂU HỎI THƯỜNG GẶP

**1. Koyeb có miễn phí không?**
Không còn. Koyeb hiện chỉ có Pro $29/tháng và Scale $299/tháng (tôi đã kiểm tra trang giá
của họ). Hugging Face cũng đã bỏ Docker Space miễn phí. Chỉ còn **Render** và **Oracle**.

**2. Web của tôi có https:// không?**
Có ✅. Render **tự động cấp HTTPS miễn phí**, link có dạng `https://app-luyen-doc.onrender.com`.
Đây là điểm mạnh hơn Oracle (Oracle muốn có HTTPS phải tự cấu hình thêm).

**3. Có gắn được tên miền riêng không?**
Được ✅. Render gói Free **hỗ trợ custom domain + chứng chỉ TLS miễn phí**. Mua 1 tên miền
(~200k/năm ở Tentenen, Mắt Bão...) → Render → **Settings** → **Custom Domains** → Add →
làm theo hướng dẫn trỏ DNS. Link sẽ thành `https://webcuaban.com`.

**4. Netlify có dùng được không?**
Không ❌. Netlify chỉ chạy file tĩnh, không chạy được Python (OCR, spaCy). App của bạn
hiện được phục vụ trọn gói bởi backend → **không cần Netlify**.

**5. Dữ liệu học viên có mất khi Render "ngủ" không?**
Không ✅. Bài viết nằm trên **Supabase** (cloud riêng), không nằm trên Render.
Render ngủ/restart cũng không ảnh hưởng gì.

**6. Bao lâu thì phải làm lại từ đầu?**
Không bao giờ ✅. Render miễn phí vĩnh viễn (không hết hạn), Supabase miễn phí vĩnh viễn
(đã có robot chống pause + dữ liệu không mất), Gemini có hạn mức miễn phí hằng ngày.

**7. Tốn bao nhiêu tiền?**
**0đ** — với điều kiện bạn chỉ dùng các gói free và **không nhập thẻ vào Render**.
Render chỉ tính tiền nếu bạn chủ động nâng cấp gói.

---

# ✅ CHECKLIST CUỐI CÙNG

**VIỆC 1 — Key Gemini**
- [ ] Tạo key Gemini mới, copy vào Notes
- [ ] **Xoá key cũ** trên aistudio.google.com/apikey
- [ ] Lưu key mới vào `python_backend/.env`

**VIỆC 2 — GitHub**
- [ ] Tạo repo `app-luyen-doc` (**Public**)
- [ ] Push code lên thành công
- [ ] Đã kiểm tra `.env` **không** bị đẩy lên

**VIỆC 3 — Render**
- [ ] Tạo tài khoản Render (không cần thẻ)
- [ ] New Web Service → chọn repo → Runtime **Docker** → Plan **Free** → Region **Singapore**
- [ ] Thêm biến `GEMINI_API_KEY` + `ALLOWED_ORIGINS`
- [ ] Trạng thái **Live** + mở link thấy web

**VIỆC 4 — Supabase**
- [ ] Chạy SQL bật RLS → "Success. No rows returned"
- [ ] Bảng `articles` hiện **RLS enabled** 🔒
- [ ] Điền Site URL + Redirect URLs = link Render

**VIỆC 5 — Chống pause Supabase**
- [ ] Tab **Actions** có workflow "Giu Supabase hoat dong"
- [ ] Đã **Run workflow** thử → ✅ xanh

**VIỆC 6 — Chống ngủ đông**
- [ ] Tab **Actions** có workflow **"Giu web Render thuc"** (robot GitHub, chỉ chạy 06:00–23:00)
- [ ] (Tùy chọn) Thêm cron-job.org làm lớp dự phòng thứ 2
- [ ] Vào web buổi sáng thấy hiện **ngay** (không chờ)

**VIỆC 7 — Kiểm tra**
- [ ] Đăng ký + đăng nhập OK
- [ ] Phân tích từ vựng OK (Gemini chạy)
- [ ] Upload PDF nhỏ OK (OCR chạy)
- [ ] Lưu bài → F5 → bài vẫn còn (RLS đúng)

---

# 💡 VÀI SỰ THẬT NÊN BIẾT

- **App của bạn rất nhẹ.** Tôi đã đo thực tế: chạy đầy đủ backend chỉ tốn **53 MB RAM**
  (Render Free cho 512 MB) → thoải mái. Đây là lý do bạn **không cần** Oracle để chạy được web.
- **Điểm yếu thật của Render Free** không phải RAM mà là **0.1 CPU** + **ngủ đông**.
  Nếu bạn thường xuyên xử lý PDF dài thì đó là lúc đáng cân nhắc Oracle.
- **Bảo mật:** repo Public nghĩa là ai cũng đọc được code, nhưng **không** đọc được key
  Gemini (đã chuyển vào biến môi trường) và **không** sửa được dữ liệu người khác (đã có RLS).
- **Đừng nhập thẻ vào Render** nếu muốn chắc chắn 0đ. Gói Free không cần thẻ.
- **Sao lưu:** code nằm trên GitHub = đã có bản sao. Dữ liệu nằm trên Supabase = hãy thỉnh
  thoảng vào **Database → Backups** xem qua.
