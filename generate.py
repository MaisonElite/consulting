# -*- coding: utf-8 -*-
"""메종엘리트 자동 글 발행 스크립트.
실행 1회 = 개인(칼럼) 1편 + 사업자(인사이트) 1편 생성·발행.
GitHub Actions가 하루 2회 실행 → 하루 4편.
"""
import os, re, json, random, datetime, urllib.request, html as htmlmod, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO = os.path.join(ROOT, 'automation')
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MODEL = 'claude-sonnet-4-6'
TODAY = datetime.date.today().isoformat()

BANNED = ['반드시', '최고의', '지금 바로', '절대적으로', '획기적', '혁신적인 솔루션', '—', '–']

def load(p, d=None):
    try:
        with open(p, encoding='utf-8') as f: return json.load(f)
    except Exception: return d

def save(p, obj):
    with open(p, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=1)

def call_claude(system, user):
    body = json.dumps({
        'model': MODEL, 'max_tokens': 4000,
        'system': system,
        'messages': [{'role': 'user', 'content': user}]
    }).encode()
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, headers={
        'content-type': 'application/json', 'x-api-key': API_KEY, 'anthropic-version': '2023-06-01'})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return ''.join(b.get('text', '') for b in out.get('content', []))

SYSTEM = """당신은 메종엘리트의 콘텐츠를 쓰는 전문 작가다. 개인 인생 상담(칼럼)과 정부지원사업 컨설팅(인사이트) 두 분야의 글을 쓴다.

[절대 규칙 - 위반 시 글 폐기]
1. 구체적 경험담·사례·통계를 지어내지 마라. "제가 상담한 A씨", "열에 일곱은", "작년에 겪은 일" 같은 허구 금지. 대신 일반화된 전문가 관점("이런 경우가 흔하다", "많은 사람이 이 지점에서 놓친다")과 구조적 통찰, 강한 단언으로 승부하라.
2. 홍보성 표현 금지: 반드시, 최고의, 지금 바로, 획기적. 정보체로 담백하게.
3. 긴 대시(—, –) 사용 금지. 쉼표와 마침표로 리듬을 만들라.
4. 본문에 <br> 같은 강제 줄바꿈 금지. 문장은 자연스럽게 흐르게.
5. 평어체(~다)로 쓴다. 단호하고 뼈 때리는 톤. 하지만 독자를 깔보지 않는다.

[반복 금지 - 매우 중요]
직전에 발행된 글들의 제목과 도입부가 제공된다. 그 글들과 도입 방식, 문장 패턴, 구조 표현이 겹치면 안 된다. "결론부터.", "먼저 이 사실을 받아들여야 한다" 같은 표현을 이미 쓴 글이 있다면 절대 재사용하지 마라. 매 글은 처음 읽는 사람에게 새로운 호흡이어야 한다.

[출력 형식]
반드시 아래 JSON만 출력하라. 마크다운 코드펜스, 설명, 인사말 전부 금지. JSON 외 텍스트가 한 글자라도 있으면 실패다.
{
 "title": "글 제목 (주제를 그대로 쓰지 말고 더 날카롭게 벼려라)",
 "slug": "영문-소문자-하이픈-slug (한글 금지, 4~6단어)",
 "excerpt": "목록 카드에 보일 요약 1~2문장",
 "tag": "카테고리 태그 (예: 진로, 관계, 서류 전략, 정산)",
 "lede_label": "도입 박스 라벨 (예: 한 줄 결론, 핵심, 먼저 답부터)",
 "lede": "글 전체의 결론을 담은 도입 문단. 2~3문장. <b>태그로 핵심 강조 가능.",
 "sections": [
  {"h2": "소제목", "paras": ["문단1", "문단2"]},
  {"h2": "소제목", "paras": ["문단1"]}
 ],
 "visual": {"type": "cols", "bad_h": "왼쪽 제목", "bad": ["항목1","항목2","항목3"], "good_h": "오른쪽 제목", "good": ["항목1","항목2","항목3"]},
 "tip_label": "강조 박스 라벨 (예: 자가 테스트, 오늘 할 일, 스스로에게 물을 것)",
 "tip": "독자가 바로 실행할 수 있는 구체적 행동 지침. 2~3문장.",
 "faq": [{"q": "질문", "a": "답변"}, {"q": "질문", "a": "답변"}, {"q": "질문", "a": "답변"}]
}

visual.type은 주제에 맞게 셋 중 하나를 골라라:
- "cols": 대비형 (나쁜 접근 vs 좋은 접근). bad_h/bad/good_h/good 필드.
- "vs": 비교형 (두 개념 비교). 필드: a_t, a_s, a_p, b_t, b_s, b_p (제목/부제/설명).
- "steps": 순서형 (단계별 행동). 필드: items: [{"n":"1","t":"제목","p":"설명"}, ...] 3~4개.

sections는 3~4개. 각 섹션 문단은 2~3개, 문단당 2~4문장. 전체 분량은 읽는 데 4~5분.
FAQ는 실제 검색될 법한 질문으로 정확히 3개."""


def build_prompt(category, topic, recent):
    cat_ko = '개인 인생 칼럼' if category == 'personal' else '정부지원사업 인사이트'
    tone = ('진로, 관계, 결정, 감정을 다루는 칼럼이다. 상담자의 시선으로, 위로 대신 정리를 준다. '
            '읽는 사람이 자기 상황을 객관화하게 만들라.') if category == 'personal' else (
           '정부지원사업(사업계획서, 심사, 발표, 정산, 정책자금)의 실전 인사이트다. '
           '지원자 대부분이 모르는 심사·행정의 작동 원리를 파헤쳐라. 막연한 격려 금지, 구조와 기준을 보여줘라.')
    rec = '\n'.join('- ' + r['title'] + ' / 도입: ' + r['opening'][:80] for r in recent[-8:]) or '(없음)'
    return (f'카테고리: {cat_ko}\n주제: {topic}\n\n[최근 발행 글 - 이것들과 겹치지 않게]\n{rec}\n\n'
            f'[톤 지침]\n{tone}\n\n위 주제로 JSON을 출력하라.')


def extract_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(json)?\s*|\s*```$', '', text, flags=re.S)
    s, e = text.find('{'), text.rfind('}')
    return json.loads(text[s:e+1])


def quality_gate(art, recent):
    joined = json.dumps(art, ensure_ascii=False)
    for w in BANNED:
        if w in joined:
            return f'금칙어 포함: {w}'
    if len(art.get('sections', [])) < 3:
        return '섹션 부족'
    if len(art.get('faq', [])) != 3:
        return 'FAQ 3개 아님'
    body = ' '.join(p for s in art['sections'] for p in s['paras'])
    if len(body) < 800:
        return f'본문 너무 짧음({len(body)}자)'
    # 지어낸 경험담 패턴 검사
    for pat in [r'제가\s*(상담|컨설팅)한', r'\d+년에\s*겪', r'열에\s*[일둘셋넷다]']:
        if re.search(pat, joined):
            return '허구 경험담 패턴 감지'
    # 최근 글과 제목 유사도(단어 겹침) 검사
    tw = set(re.findall(r'[가-힣]{2,}', art['title']))
    for r in recent[-15:]:
        rw = set(re.findall(r'[가-힣]{2,}', r['title']))
        if tw and len(tw & rw) / len(tw | rw) > 0.6:
            return '최근 글과 제목 유사'
    return None


def esc(s):
    return htmlmod.escape(str(s), quote=False)


def render_visual(v):
    t = v.get('type')
    if t == 'cols':
        li = lambda arr: ''.join(f'<li>{esc(x)}</li>' for x in arr)
        return (f'<div class="cols"><div class="col bad"><div class="h">✕ {esc(v["bad_h"])}</div>'
                f'<ul>{li(v["bad"])}</ul></div><div class="col good"><div class="h">✓ {esc(v["good_h"])}</div>'
                f'<ul>{li(v["good"])}</ul></div></div>')
    if t == 'vs':
        return (f'<div class="vs"><div class="vs-row"><div class="vs-cell"><div class="t">{esc(v["a_t"])}</div>'
                f'<div class="s">{esc(v["a_s"])}</div><p>{esc(v["a_p"])}</p></div>'
                f'<div class="vs-cell"><div class="t">{esc(v["b_t"])}</div><div class="s">{esc(v["b_s"])}</div>'
                f'<p>{esc(v["b_p"])}</p></div></div></div>')
    if t == 'steps':
        rows = ''.join(f'<div class="step"><div class="n">{esc(i["n"])}</div><div><div class="t">{esc(i["t"])}</div>'
                       f'<p>{esc(i["p"])}</p></div></div>' for i in v.get('items', []))
        return f'<div class="steps">{rows}</div>'
    return ''


def render_page(art, category):
    tpl = open(os.path.join(AUTO, 'template.html'), encoding='utf-8').read()
    cat_label = '칼럼' if category == 'personal' else '인사이트'
    back = '#personal' if category == 'personal' else '#business'
    secs = ''
    mid = max(1, len(art['sections']) // 2)
    for i, s in enumerate(art['sections']):
        secs += f'<h2>{esc(s["h2"])}</h2>' + ''.join(f'<p>{p}</p>' for p in s['paras'])
        if i == mid - 1:
            secs += render_visual(art.get('visual', {}))
    faq = ''.join(f'<details><summary>{esc(f["q"])}</summary><div class="a">{esc(f["a"])}</div></details>'
                  for f in art['faq'])
    cta_t = '상담 신청 →' if category == 'personal' else '미팅 신청 →'
    cta_href = '#p-book' if category == 'personal' else '#b-book'
    cta_n = ('60분, 결론이 나올 때까지 함께 정리합니다.' if category == 'personal'
             else '결제 전 미팅으로 먼저 만나고, 계약은 그 뒤에 정합니다.')
    for k, vv in {
        '{{TITLE}}': esc(art['title']), '{{DESC}}': esc(art['excerpt']), '{{SLUG}}': art['slug'],
        '{{DATE}}': TODAY, '{{DATE_DOT}}': TODAY.replace('-', '.'), '{{CAT}}': cat_label,
        '{{TAG}}': esc(art.get('tag', cat_label)), '{{BACK}}': back,
        '{{LEDE_LABEL}}': esc(art.get('lede_label', '한 줄 결론')), '{{LEDE}}': art['lede'],
        '{{SECTIONS}}': secs, '{{TIP_LABEL}}': esc(art.get('tip_label', '체크')), '{{TIP}}': art['tip'],
        '{{FAQ}}': faq, '{{CTA_T}}': cta_t, '{{CTA_N}}': cta_n, '{{CTA_HREF}}': cta_href,
    }.items():
        tpl = tpl.replace(k, vv)
    return tpl


def publish(art, category):
    slug = re.sub(r'[^a-z0-9-]', '', art['slug'].lower())[:60] or ('post-' + TODAY)
    path = f'insights/{slug}.html'
    full = os.path.join(ROOT, path)
    if os.path.exists(full):
        slug += '-' + datetime.datetime.now().strftime('%H%M')
        path = f'insights/{slug}.html'
        full = os.path.join(ROOT, path)
    open(full, 'w', encoding='utf-8').write(render_page(art, category))

    # index.html POSTS 배열에 카드 추가 (마커 뒤 삽입 = 최신이 앞)
    idx_p = os.path.join(ROOT, 'index.html')
    idx = open(idx_p, encoding='utf-8').read()
    marker = '/*@P*/' if category == 'personal' else '/*@B*/'
    entry = ('\n      {title:' + json.dumps(art['title'], ensure_ascii=False) +
             ', excerpt:' + json.dumps(art['excerpt'], ensure_ascii=False) +
             ", date:'" + TODAY + "', url:'" + path + "', tag:" +
             json.dumps(art.get('tag', ''), ensure_ascii=False) + '},')
    idx = idx.replace(marker, marker + entry, 1)
    open(idx_p, 'w', encoding='utf-8').write(idx)

    # sitemap.xml 추가
    sm_p = os.path.join(ROOT, 'sitemap.xml')
    sm = open(sm_p, encoding='utf-8').read()
    url = (f'  <url>\n    <loc>https://maisonelite.co.kr/{path}</loc>\n'
           f'    <lastmod>{TODAY}</lastmod>\n    <changefreq>monthly</changefreq>\n'
           f'    <priority>0.8</priority>\n  </url>\n</urlset>')
    sm = sm.replace('</urlset>', url)
    open(sm_p, 'w', encoding='utf-8').write(sm)
    return path


def run_one(category, topics, recent):
    pool = [t for t in topics[category] if not t['used']]
    if not pool:
        print(f'[{category}] 주제 소진'); return None
    pick = pool[0]
    for attempt in range(3):
        try:
            raw = call_claude(SYSTEM, build_prompt(category, pick['topic'], recent))
            art = extract_json(raw)
            err = quality_gate(art, recent)
            if err:
                print(f'[{category}] 재시도({attempt+1}): {err}'); continue
            path = publish(art, category)
            pick['used'] = True
            recent.append({'title': art['title'], 'opening': art['lede'][:120], 'date': TODAY, 'path': path})
            print(f'[{category}] 발행: {art["title"]} → {path}')
            return path
        except Exception as e:
            print(f'[{category}] 오류({attempt+1}): {e}')
    print(f'[{category}] 3회 실패, 이번 회차 건너뜀')
    return None


def main():
    if not API_KEY:
        print('ANTHROPIC_API_KEY 없음'); sys.exit(1)
    # 주말 변동: 토/일은 40% 확률로 이번 실행 스킵 (기계적 규칙성 제거)
    wd = datetime.date.today().weekday()
    if wd >= 5 and random.random() < 0.4:
        print('주말 변동: 이번 회차 스킵'); return
    topics = load(os.path.join(AUTO, 'topics.json'), {'personal': [], 'business': []})
    recent = load(os.path.join(AUTO, 'recent.json'), [])
    for cat in ('personal', 'business'):
        run_one(cat, topics, recent)
    save(os.path.join(AUTO, 'topics.json'), topics)
    save(os.path.join(AUTO, 'recent.json'), recent[-60:])


if __name__ == '__main__':
    main()
