# YouTube Content Dictionary v1

## Mục đích

File này là từ điển phân loại nội dung dùng chung cho toàn bộ dự án. Nó phục vụ ba việc:

1. Phân loại một video vào một hoặc nhiều nhóm nội dung.
2. Sinh và cập nhật hồ sơ sở thích của Viewer Robot.
3. Cho Creator Model chọn nhóm nội dung/audience mục tiêu trong môi trường mô phỏng.

Một video có thể thuộc nhiều nhóm với trọng số khác nhau. `Category` là tầng cao nhất; bên dưới là `Niche` và `Topic`.

> Tham chiếu YouTube: YouTube Data API có `videoCategory` cho category video và `topicDetails`/topic IDs cho một số chủ đề lớn. Taxonomy dưới đây là taxonomy nội bộ mở rộng của dự án, không phải tuyên bố rằng YouTube chỉ có đúng 18 nhóm này.

---

# 1. Entertainment — Giải trí

**ID:** `entertainment`

**YouTube reference:** Video Category 24 — Entertainment; topic parent `/m/02jjt`.

**Phạm vi:** Nội dung chủ yếu nhằm giải trí, theo dõi người nổi tiếng, chương trình, xu hướng, biểu diễn hoặc nội dung viral.

### Niches / Topics

- `celebrity_showbiz` — người nổi tiếng, showbiz, idol, scandal, hậu trường
- `reality_tv` — reality show, chương trình thực tế, dating show
- `variety_talk_show` — variety show, talk show, game show
- `reaction` — reaction, reacting, phản ứng
- `challenge_viral` — challenge, thử thách, viral trend, trending
- `talent_show` — talent show, audition, cuộc thi tài năng
- `awards_events` — award show, lễ trao giải, red carpet
- `performing_arts` — biểu diễn, sân khấu, performance

**Keywords VI:** giải trí, showbiz, người nổi tiếng, thần tượng, chương trình thực tế, talk show, thử thách, reaction, viral, xu hướng, hậu trường, lễ trao giải

**Keywords EN:** entertainment, celebrity, showbiz, idol, reality show, talk show, variety show, reaction, challenge, viral, trending, awards, performance

**Liên quan:** `comedy`, `music`, `film_animation`, `people_lifestyle`, `gaming`

---

# 2. News & Politics — Tin tức & Chính trị

**ID:** `news_politics`

**YouTube reference:** Video Category 25 — News & Politics; politics topic `/m/05qt0`.

**Phạm vi:** Tin mới, thời sự, chính trị, chính sách, quan hệ quốc tế, an ninh và các vấn đề xã hội đương thời.

### Niches / Topics

- `breaking_news` — breaking news, tin nóng, tin mới
- `domestic_news` — tin trong nước, local news
- `world_news` — international news, world news
- `politics_elections` — chính trị, bầu cử, election, parliament, government
- `geopolitics_diplomacy` — địa chính trị, ngoại giao, diplomacy
- `military_security` — quân sự, quốc phòng, security, defense
- `economy_policy` — chính sách kinh tế, lạm phát, ngân sách, central bank
- `law_crime` — pháp luật, tòa án, crime, investigation
- `analysis_commentary` — phân tích thời sự, commentary, opinion

**Keywords VI:** tin tức, tin nóng, thời sự, chính trị, bầu cử, chính phủ, quốc hội, địa chính trị, ngoại giao, quân sự, quốc phòng, pháp luật, kinh tế vĩ mô

**Keywords EN:** news, breaking news, politics, election, government, parliament, geopolitics, diplomacy, military, defense, law, crime, current affairs, policy

**Liên quan:** `business_finance`, `society_community`, `science_technology`

---

# 3. Music — Âm nhạc

**ID:** `music`

**YouTube reference:** Video Category 10 — Music; parent topic `/m/04rlf`.

### Niches / Topics

- `pop` — pop, V-pop, K-pop, J-pop
- `rock` — rock, alternative rock, metal
- `hiphop_rap` — hip hop, rap, trap
- `electronic` — EDM, electronic, house, techno
- `rnb_soul` — R&B, soul
- `jazz` — jazz
- `classical` — classical, orchestra, piano, violin
- `asian_music` — Asian music, K-pop, J-pop, C-pop, V-pop
- `live_performance` — live, concert, performance
- `cover_remix` — cover, remix, mashup
- `music_theory` — music theory, production, songwriting

**Keywords VI:** âm nhạc, bài hát, ca sĩ, album, MV, lời bài hát, concert, biểu diễn, remix, cover, nhạc pop, rap, rock, EDM

**Keywords EN:** music, song, singer, artist, album, music video, lyrics, concert, live performance, remix, cover, pop, rap, hip hop, rock, EDM

**Liên quan:** `entertainment`, `film_animation`, `people_lifestyle`

---

# 4. Gaming — Trò chơi

**ID:** `gaming`

**YouTube reference:** Video Category 20 — Gaming; parent topic `/m/0bzvm2`.

### Niches / Topics

- `action` — action game
- `action_adventure` — action-adventure
- `casual_puzzle` — casual game, puzzle game
- `racing` — racing game
- `rpg` — RPG, role-playing
- `simulation` — simulation, simulator
- `sports_games` — football game, sports game
- `strategy` — strategy, RTS, turn-based
- `fps` — FPS, shooter
- `moba` — MOBA
- `mobile_gaming` — mobile game
- `esports` — esports, tournament, competitive gaming
- `gameplay_guides` — gameplay, walkthrough, playthrough, tips, build guide
- `gaming_news_reviews` — gaming news, review, patch notes

**Keywords VI:** game, trò chơi, gameplay, game thủ, hướng dẫn game, esports, giải đấu, game mobile, nhập vai, chiến thuật, bắn súng

**Keywords EN:** gaming, game, gameplay, gamer, walkthrough, playthrough, esports, RPG, FPS, MOBA, strategy, simulator, mobile game, game review

**Liên quan:** `entertainment`, `science_technology`, `sports`

---

# 5. Sports — Thể thao

**ID:** `sports`

**YouTube reference:** Video Category 17 — Sports; parent topic `/m/06ntj`.

### Niches / Topics

- `football_soccer` — football, soccer, bóng đá
- `basketball` — basketball, NBA
- `tennis` — tennis
- `volleyball` — volleyball
- `combat_sports` — boxing, MMA, UFC, martial arts
- `motorsport` — Formula 1, MotoGP, racing
- `baseball_cricket` — baseball, cricket
- `golf` — golf
- `american_football` — NFL, American football
- `training_analysis` — training, tactics, match analysis
- `highlights_results` — highlights, results, recap

**Keywords VI:** thể thao, bóng đá, bóng rổ, quần vợt, bóng chuyền, quyền anh, MMA, đua xe, golf, trận đấu, highlights, chiến thuật

**Keywords EN:** sports, football, soccer, basketball, tennis, volleyball, boxing, MMA, motorsport, golf, match, highlights, athlete, training

**Liên quan:** `health_fitness`, `gaming`, `news_politics`

---

# 6. Film & Animation — Phim & Hoạt hình

**ID:** `film_animation`

**YouTube reference:** Video Category 1 — Film & Animation; movie topic `/m/02vxn`, TV shows `/m/0f2f9`.

### Niches / Topics

- `movies` — movies, cinema, film
- `tv_series` — TV series, series, television
- `anime` — anime, manga adaptation
- `animation` — animation, animated short
- `documentary` — documentary
- `trailers_clips` — trailer, teaser, clip
- `reviews` — movie review, series review
- `explained_analysis` — ending explained, movie analysis, lore
- `filmmaking` — filmmaking, cinematography, directing, VFX

**Keywords VI:** phim, điện ảnh, hoạt hình, anime, phim truyền hình, trailer, review phim, giải thích phim, tài liệu, đạo diễn

**Keywords EN:** film, movie, cinema, animation, anime, TV series, trailer, review, ending explained, documentary, filmmaking, cinematography

**Liên quan:** `entertainment`, `music`, `comedy`

---

# 7. Education — Giáo dục

**ID:** `education`

**YouTube reference:** Video Category 27 — Education; knowledge topic `/m/01k8wb`.

### Niches / Topics

- `mathematics` — mathematics, algebra, calculus, geometry
- `science_learning` — physics, chemistry, biology lessons
- `history_geography` — history, geography
- `language_learning` — English, language learning, grammar, vocabulary
- `exam_preparation` — exam, test prep, SAT, IELTS, TOEIC
- `study_skills` — study method, memory, note-taking
- `career_skills` — professional skills, career learning
- `lectures_courses` — course, lecture, class
- `general_knowledge` — facts, knowledge, explainer

**Keywords VI:** giáo dục, học tập, bài giảng, khóa học, toán, vật lý, hóa học, sinh học, lịch sử, địa lý, học tiếng Anh, luyện thi, kiến thức

**Keywords EN:** education, learning, lesson, course, lecture, mathematics, physics, chemistry, biology, history, language learning, exam preparation, study

**Liên quan:** `science_technology`, `business_finance`, `health_fitness`, `society_community`

---

# 8. Science & Technology — Khoa học & Công nghệ

**ID:** `science_technology`

**YouTube reference:** Video Category 28 — Science & Technology; technology topic `/m/07c1v`.

### Niches / Topics

- `artificial_intelligence` — AI, artificial intelligence, generative AI, LLM
- `ai_agents` — AI agent, agentic AI, tool calling, MCP, multi-agent
- `machine_learning` — machine learning, deep learning, neural network
- `programming` — coding, programming, Python, JavaScript, software development
- `software` — software, apps, SaaS, operating systems
- `hardware_computing` — CPU, GPU, PC, computer hardware
- `consumer_technology` — smartphone, laptop, wearable, gadgets
- `cybersecurity` — cybersecurity, security, hacking, privacy
- `robotics_electronics` — robotics, electronics, microcontroller, Arduino
- `space_astronomy` — space, astronomy, NASA, rockets
- `science_general` — physics, biology, chemistry, scientific discoveries

**Keywords VI:** công nghệ, khoa học, trí tuệ nhân tạo, AI, lập trình, phần mềm, máy tính, điện thoại, an ninh mạng, robot, điện tử, vũ trụ

**Keywords EN:** technology, science, artificial intelligence, AI, LLM, programming, coding, software, hardware, cybersecurity, robotics, electronics, space, astronomy

**Liên quan:** `education`, `business_finance`, `gaming`, `news_politics`, `autos_vehicles`

---

# 9. People & Lifestyle — Con người & Cuộc sống

**ID:** `people_lifestyle`

**YouTube reference:** Video Category 22 — People & Blogs; lifestyle topic `/m/019_rr`.

### Niches / Topics

- `daily_vlog` — vlog, daily vlog, day in my life
- `family_parenting` — family, parenting, motherhood, fatherhood
- `relationships` — dating, relationship, marriage
- `personal_story` — storytime, personal experience
- `student_life` — student life, campus, study vlog
- `work_life` — office life, career vlog, workday
- `routine` — morning routine, night routine
- `hobbies` — hobby, collecting, personal interests
- `self_development` — personal growth, habits, life advice

**Keywords VI:** vlog, cuộc sống, gia đình, tình yêu, hẹn hò, nuôi dạy con, câu chuyện cá nhân, đời sống sinh viên, công việc, thói quen

**Keywords EN:** vlog, lifestyle, daily life, family, parenting, relationship, dating, storytime, student life, work life, routine, personal growth

**Liên quan:** `entertainment`, `howto_style`, `travel_events`, `food_cooking`, `health_fitness`

---

# 10. How-to & Style — Hướng dẫn & Phong cách

**ID:** `howto_style`

**YouTube reference:** Video Category 26 — Howto & Style; fashion `/m/032tl`, beauty `/m/041xxh`.

### Niches / Topics

- `diy` — DIY, tự làm, repair tutorial
- `fashion` — fashion, outfit, clothing, styling
- `beauty_makeup` — beauty, makeup, cosmetics
- `skincare_hair` — skincare, haircare, hairstyle
- `home_garden` — home improvement, interior, gardening
- `crafts` — crafts, handmade
- `productivity` — productivity, workflow, organization
- `life_hacks` — life hack, tips and tricks

**Keywords VI:** hướng dẫn, cách làm, DIY, thời trang, làm đẹp, trang điểm, chăm sóc da, tóc, nhà cửa, làm vườn, thủ công, năng suất, mẹo

**Keywords EN:** how to, tutorial, DIY, fashion, style, beauty, makeup, skincare, hair, home improvement, gardening, crafts, productivity, life hacks

**Liên quan:** `people_lifestyle`, `food_cooking`, `health_fitness`, `autos_vehicles`

---

# 11. Travel & Events — Du lịch & Sự kiện

**ID:** `travel_events`

**YouTube reference:** Video Category 19 — Travel & Events; tourism topic `/m/07bxq`.

### Niches / Topics

- `destination_guides` — destination, travel guide, city guide
- `travel_vlog` — travel vlog, trip diary
- `hotels_resorts` — hotel, resort, accommodation
- `flights_airports` — flight, airline, airport
- `backpacking` — backpacking, budget travel
- `luxury_travel` — luxury hotel, business class, premium travel
- `festivals_events` — festival, convention, event
- `camping_outdoors` — camping, hiking, outdoor trip
- `food_travel` — food tour, culinary travel

**Keywords VI:** du lịch, điểm đến, khách sạn, resort, chuyến bay, sân bay, phượt, backpacking, lễ hội, sự kiện, cắm trại, review địa điểm

**Keywords EN:** travel, tourism, destination, hotel, resort, flight, airport, backpacking, travel guide, festival, event, camping, food tour

**Liên quan:** `food_cooking`, `people_lifestyle`, `autos_vehicles`

---

# 12. Autos & Vehicles — Xe & Phương tiện

**ID:** `autos_vehicles`

**YouTube reference:** Video Category 2 — Autos & Vehicles; vehicles topic `/m/07yv9`.

### Niches / Topics

- `cars` — car, automobile, sedan, SUV
- `motorcycles` — motorcycle, motorbike
- `electric_vehicles` — EV, electric car, battery vehicle
- `supercars_performance` — supercar, sports car, performance
- `reviews_test_drives` — car review, test drive
- `repair_maintenance` — repair, maintenance, mechanic
- `modification_tuning` — tuning, modification, custom car
- `aviation_transport` — aircraft, aviation, train, transport

**Keywords VI:** ô tô, xe hơi, xe máy, xe điện, siêu xe, lái thử, review xe, sửa xe, bảo dưỡng, độ xe, hàng không

**Keywords EN:** car, automobile, motorcycle, vehicle, EV, electric car, supercar, test drive, car review, repair, maintenance, tuning, aviation

**Liên quan:** `science_technology`, `sports`, `howto_style`, `travel_events`

---

# 13. Pets & Animals — Thú cưng & Động vật

**ID:** `pets_animals`

**YouTube reference:** Video Category 15 — Pets & Animals; pets topic `/m/068hy`.

### Niches / Topics

- `dogs` — dog, puppy
- `cats` — cat, kitten
- `birds` — bird, parrot
- `fish_aquatic` — aquarium, fish
- `reptiles_exotic` — reptile, snake, exotic pets
- `wildlife` — wildlife, wild animals
- `animal_rescue` — animal rescue, rehabilitation
- `pet_care_training` — pet care, dog training, veterinary
- `funny_animals` — funny pets, cute animals

**Keywords VI:** thú cưng, động vật, chó, mèo, chim, cá, bò sát, động vật hoang dã, cứu hộ động vật, chăm sóc thú cưng, huấn luyện chó

**Keywords EN:** pets, animals, dog, cat, bird, fish, reptile, wildlife, animal rescue, pet care, dog training, veterinary, funny animals

**Liên quan:** `people_lifestyle`, `education`, `entertainment`

---

# 14. Comedy — Hài

**ID:** `comedy`

**YouTube reference:** Video Category 23 — Comedy; humor topic `/m/09kqc`.

### Niches / Topics

- `standup` — stand-up comedy
- `sketch` — comedy sketch, skit
- `parody_satire` — parody, satire
- `prank` — prank
- `meme` — meme, internet humor
- `roast` — roast, comedic commentary
- `funny_moments` — funny moments, bloopers
- `improv` — improv, improvisational comedy

**Keywords VI:** hài, hài độc thoại, tiểu phẩm, châm biếm, nhại, prank, meme, troll, khoảnh khắc hài, blooper

**Keywords EN:** comedy, funny, stand-up, sketch, skit, parody, satire, prank, meme, roast, blooper, improv

**Liên quan:** `entertainment`, `people_lifestyle`, `film_animation`

---

# 15. Society & Community — Xã hội & Cộng đồng

**ID:** `society_community`

**YouTube reference:** Internal category; society topic `/m/098wr`, religion `/m/06bvp`, military `/m/01h6rj`.

### Niches / Topics

- `social_issues` — social issues, inequality, public debate
- `community` — community, local community
- `nonprofit_charity` — nonprofit, charity, volunteering
- `environment` — environment, climate, conservation
- `human_rights` — human rights, civil rights
- `religion` — religion, faith, spirituality
- `activism` — activism, campaign, advocacy
- `military_society` — military affairs in social context

**Keywords VI:** xã hội, cộng đồng, từ thiện, phi lợi nhuận, môi trường, khí hậu, nhân quyền, tôn giáo, hoạt động xã hội, tình nguyện

**Keywords EN:** society, community, nonprofit, charity, volunteering, environment, climate, human rights, religion, activism, advocacy

**Liên quan:** `news_politics`, `education`, `business_finance`

---

# 16. Business & Finance — Kinh doanh & Tài chính

**ID:** `business_finance`

**YouTube reference:** Internal category; business topic `/m/09s1f`.

### Niches / Topics

- `entrepreneurship` — entrepreneur, entrepreneurship, founder
- `startups` — startup, venture capital, fundraising
- `marketing_sales` — marketing, sales, advertising, branding
- `management_career` — management, leadership, career
- `personal_finance` — personal finance, budgeting, saving, debt
- `investing_stocks` — investing, stocks, equity, ETF
- `real_estate` — real estate, property investment
- `economics` — economics, macroeconomics, inflation
- `crypto` — crypto, cryptocurrency, blockchain, Bitcoin
- `ecommerce` — ecommerce, online business, dropshipping

**Keywords VI:** kinh doanh, tài chính, doanh nhân, startup, marketing, bán hàng, quản trị, tiền bạc, đầu tư, chứng khoán, cổ phiếu, bất động sản, kinh tế, crypto

**Keywords EN:** business, finance, entrepreneurship, startup, marketing, sales, management, personal finance, investing, stock market, real estate, economics, crypto, ecommerce

**Liên quan:** `news_politics`, `education`, `science_technology`

---

# 17. Health & Fitness — Sức khỏe & Thể chất

**ID:** `health_fitness`

**YouTube reference:** Internal category; health topic `/m/0kt51`, fitness topic `/m/027x7n`.

### Niches / Topics

- `fitness_workouts` — fitness, workout, gym, strength training
- `running_endurance` — running, marathon, cycling endurance
- `yoga_mobility` — yoga, stretching, mobility
- `nutrition` — nutrition, diet, macros, healthy eating
- `weight_management` — weight loss, fat loss, weight gain
- `mental_wellness` — mental wellness, stress, mindfulness
- `sleep_recovery` — sleep, recovery, rest
- `medical_education` — medical education, anatomy, disease explainer
- `healthy_lifestyle` — healthy habits, wellness

**Keywords VI:** sức khỏe, thể hình, tập gym, workout, chạy bộ, yoga, dinh dưỡng, giảm cân, sức khỏe tinh thần, thiền, giấc ngủ, y khoa

**Keywords EN:** health, fitness, workout, gym, running, yoga, nutrition, diet, weight loss, mental wellness, meditation, sleep, medical education, healthy lifestyle

**Liên quan:** `sports`, `food_cooking`, `education`, `howto_style`

---

# 18. Food & Cooking — Ẩm thực

**ID:** `food_cooking`

**YouTube reference:** Internal category; food topic `/m/02wbm`.

### Niches / Topics

- `recipes` — recipe, cooking, home cooking
- `street_food` — street food, local food
- `restaurant_reviews` — restaurant review, food review
- `baking` — baking, cake, bread, pastry
- `drinks_coffee` — coffee, tea, cocktails/non-alcoholic drinks
- `healthy_food` — healthy food, meal prep
- `regional_cuisine` — Vietnamese food, Japanese food, Korean food, regional cuisine
- `food_challenges_mukbang` — food challenge, mukbang
- `culinary_skills` — knife skills, cooking technique, chef skills

**Keywords VI:** ẩm thực, nấu ăn, công thức, món ăn, đồ ăn đường phố, nhà hàng, review đồ ăn, làm bánh, cà phê, meal prep, mukbang, đầu bếp

**Keywords EN:** food, cooking, recipe, street food, restaurant, food review, baking, coffee, meal prep, cuisine, food challenge, mukbang, chef, culinary

**Liên quan:** `travel_events`, `health_fitness`, `people_lifestyle`, `howto_style`

---

# 19. Quy tắc mở rộng từ điển

Khi thêm một `Niche` hoặc `Topic`, phải có tối thiểu:

```text
id
name_vi
name_en
parent
keywords_vi
keywords_en
related_topics
```

Chỉ tạo node mới nếu node đó giúp ít nhất một việc:

- phân loại video chính xác hơn;
- phân biệt hai nhóm audience khác nhau;
- mô tả được một sở thích thực tế của viewer;
- creator có thể chủ động nhắm nội dung vào nhóm đó.

Không dùng format như `Shorts`, `Live`, `Podcast` làm Category nội dung. Format phải được lưu thành dimension riêng.

---

# 20. Các dimension không phải Category

Khi classify video, ngoài Content Category còn cần các dimension độc lập:

## Format

`shorts`, `long_form`, `podcast`, `livestream`, `clip`, `series`, `course`

## Content intent

`tutorial`, `news`, `review`, `comparison`, `analysis`, `opinion`, `reaction`, `storytelling`, `documentary`, `entertainment`, `case_study`, `experiment`

## Audience level

`beginner`, `intermediate`, `advanced`, `professional`, `general_audience`

Các dimension này không thay thế Category. Ví dụ một video có thể là:

```text
Category: Science & Technology
Topic: AI Agents
Intent: Tutorial
Format: Long-form
Audience level: Intermediate
```

---

# 21. Lưu ý về nguồn tham chiếu YouTube

YouTube Data API cung cấp `videoCategories.list`; danh sách category có thể phụ thuộc `regionCode` và mỗi category có thuộc tính `assignable`. YouTube cũng công bố một tập topic IDs hỗ trợ cho các nhánh như Music, Gaming, Sports, Entertainment, Lifestyle, Society và Knowledge. Taxonomy nội bộ của dự án mở rộng các nhóm này để phục vụ mô phỏng hành vi và targeting, vì vậy không được đồng nhất `internal_category_id` với `youtube_video_category_id`.
