# Facts LLM prompt (layer B)

Извлеки ФИО, роли и поручения из текста страницы Confluence.
Верни только JSON по схеме. Каждая запись обязана содержать source_page_id и confidence.
Не выдумывай факты. Цифры и даты не извлекай — они в script_only.
