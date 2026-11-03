// Set-of-Mark (SoM) Ingestion Engine for RPA Vagas (Candidato Modelo)
// Renderiza Bounding Boxes de alto contraste com selos numéricos espaciais [ID]
// e diagnostica modais, banners de cookies e captchas.

window.clearSetOfMark = function() {
    document.querySelectorAll('.som-marker-box, .som-marker-label').forEach(el => el.remove());
};

window.applySetOfMark = function() {
    // 1. Limpeza defensiva de marcações anteriores
    window.clearSetOfMark();

    let idCounter = 1;
    let bboxes = [];
    let hasModal = false;
    let hasCaptcha = false;
    let modalDismissId = null;

    // Detecção direta de Captcha (reCAPTCHA, hCaptcha, Turnstile)
    const captchaElements = document.querySelectorAll(
        'iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="turnstile"], .g-recaptcha, .h-captcha, [data-sitekey]'
    );
    if (captchaElements.length > 0) {
        hasCaptcha = true;
    }

    // Seletores de elementos interativos e semânticos
    const interactiveSelectors = 'button, a, input, textarea, select, [role="button"], [role="checkbox"], [role="radio"], [role="combobox"], [role="option"], [tabindex="0"]';
    const textSelectors = 'h1, h2, h3, h4, label, p, span, div.question-title';

    const allElements = document.querySelectorAll(`${interactiveSelectors}, ${textSelectors}`);

    allElements.forEach(el => {
        // Ignorar se já for um marcador SoM
        if (el.classList && (el.classList.contains('som-marker-box') || el.classList.contains('som-marker-label'))) return;

        const rect = el.getBoundingClientRect();
        // Ignorar elementos fora do viewport, invisíveis ou insignificantes
        if (rect.width < 12 || rect.height < 12) return;
        if (rect.top < -50 || rect.left < -50 || rect.top > window.innerHeight + 100) return;

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return;

        const tag = el.tagName.toUpperCase();
        const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
        const isClickable = tag === 'BUTTON' || tag === 'A' || el.getAttribute('role') === 'button' || el.onclick != null || isInput;
        const text = (el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('aria-label') || '').trim();

        // Se for elemento puramente textual sem texto, ignora
        if (!isInput && text === '') return;

        const currentId = idCounter++;
        el.setAttribute('data-som-id', String(currentId));

        // Determinar estilo visual e semântica
        let borderColor = '#2563EB'; // Azul (interativo padrão)
        let bgColor = 'rgba(37, 99, 235, 0.12)';
        let badgeColor = '#1D4ED8';
        let elementType = 'button';

        if (isInput) {
            borderColor = '#D97706'; // Âmbar (input)
            bgColor = 'rgba(217, 119, 6, 0.14)';
            badgeColor = '#B45309';
            elementType = 'input';
        } else if (!isClickable) {
            borderColor = '#64748B'; // Slate (leitura/contexto)
            bgColor = 'rgba(100, 116, 139, 0.08)';
            badgeColor = '#475569';
            elementType = 'text';
        }

        // Diagnóstico de modal ou banner de cookies (LGPD / aceitar / fechar)
        const lowerText = text.toLowerCase();
        const isCookieOrModalAction = (
            lowerText.includes('aceitar cookies') ||
            lowerText.includes('aceitar todos') ||
            lowerText.includes('aceito') ||
            lowerText.includes('concordo') ||
            lowerText.includes('entendi') ||
            lowerText.includes('fechar') ||
            lowerText.includes('salvar preferências')
        );

        if (isCookieOrModalAction && isClickable && modalDismissId === null) {
            hasModal = true;
            modalDismissId = currentId;
            borderColor = '#16A34A'; // Verde para desobstrução rápida
            badgeColor = '#15803D';
        }

        // 2. Renderizar Caixa Delimitadora (Bounding Box)
        const box = document.createElement('div');
        box.className = 'som-marker-box';
        box.style.position = 'absolute';
        box.style.left = `${rect.left + window.scrollX}px`;
        box.style.top = `${rect.top + window.scrollY}px`;
        box.style.width = `${rect.width}px`;
        box.style.height = `${rect.height}px`;
        box.style.border = `2.5pt solid ${borderColor}`;
        box.style.backgroundColor = bgColor;
        box.style.pointerEvents = 'none';
        box.style.zIndex = '2147483640';

        // 3. Renderizar Selo Numérico
        const label = document.createElement('div');
        label.className = 'som-marker-label';
        label.innerText = `[${currentId}]`;
        label.style.position = 'absolute';
        label.style.left = `${rect.left + window.scrollX}px`;
        label.style.top = `${Math.max(0, rect.top + window.scrollY - 18)}px`;
        label.style.backgroundColor = badgeColor;
        label.style.color = '#FFFFFF';
        label.style.fontSize = '12px';
        label.style.fontFamily = 'monospace';
        label.style.fontWeight = 'bold';
        label.style.padding = '1px 5px';
        label.style.borderRadius = '3px';
        label.style.pointerEvents = 'none';
        label.style.zIndex = '2147483647';
        label.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';

        document.body.appendChild(box);
        document.body.appendChild(label);

        bboxes.push({
            id: currentId,
            tag: tag,
            type: el.type || elementType,
            text: text.substring(0, 120),
            center_x: Math.round(rect.left + window.scrollX + (rect.width / 2)),
            center_y: Math.round(rect.top + window.scrollY + (rect.height / 2)),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            is_clickable: isClickable,
            is_dismiss: isCookieOrModalAction
        });
    });

    // Retorna array de bboxes com metadados acoplados para interoperabilidade
    const resultado = {
        bboxes: bboxes,
        has_modal: hasModal,
        has_captcha: hasCaptcha,
        modal_dismiss_id: modalDismissId,
        count: bboxes.length
    };

    // Para compatibilidade com chamadas que iteram diretamente sobre o array
    bboxes.meta = resultado;
    return bboxes;
};
