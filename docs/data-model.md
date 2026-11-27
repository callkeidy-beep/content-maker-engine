# 데이터 모델

SQLite로 시작한다. 이름은 영어, 화면 표시는 한국어.
시각은 모두 UTC로 저장하고 화면에서 KST로 바꾼다.

## mail_accounts — 메일 계정
| 열 | 형 | 설명 |
|---|---|---|
| id | int | |
| provider | text | naver / daum / sample / imap |
| address | text | 메일 주소 |
| host, port | text, int | IMAP 서버 |
| folders | json | 읽을 폴더 목록 |
| status | text | connected / failed / not_configured / sample |
| last_ok_at, last_error | datetime, text | 마지막 성공, 마지막 오류(비밀번호 제외) |

비밀번호는 이 테이블에 넣지 않는다. `.env`에서만 읽는다.

## mail_sync_state — 폴더별 동기화 위치
| account_id, folder | | |
| uidvalidity | int | 바뀌면 전체 재대조 |
| last_uid | int | 여기까지 가져옴 |

## messages — 수신 메일 원본
| 열 | 설명 |
|---|---|
| id, account_id, folder, uid | |
| message_id | 헤더 Message-ID |
| from_name, from_addr, subject | |
| received_at | 수신 시각 |
| body_text, body_html | 본문 (원문 보존) |
| raw_path | .eml 원본 저장 경로 |
| dup_group_id | 중복 묶음 |

## attachments — 첨부
| id, message_id, filename, mime, size, path |
| extract_status | ok / failed / manual / link_only |
| extract_text | 추출 텍스트 |
| external_link | 대용량 첨부 링크 |

## photos — 사진
| id, attachment_id |
| width, height |
| source, provider, caption, usage_terms |
| usable | true / hold (출처 불명이면 hold) |

## items — 기사 자료 단위
메일 하나 = 자료 하나가 기본. 버전이 여러 개면 한 item에 묶는다.
| 열 | 설명 |
|---|---|
| id | |
| kind | press_release / tip |
| org, contact_name, contact_info | contact는 가린 형태로도 따로 저장 |
| category | config/categories.yaml 키 |
| title_guess | 추정 제목 |
| key_facts | json: [{text, source_ref}] |
| entities | json: people, orgs, places, numbers |
| embargo_at | 엠바고 해제 시각 (없으면 null) |
| status | 상태 흐름 참조 |
| current_version | 최신 버전 번호 |
| sensitive_class | none / disaster / accident / crime / election |

## item_versions
| item_id, version, message_id, diff_summary, created_at |

## source_refs — 근거 위치
모든 사실은 여기로 돌아온다.
| id | |
| item_id | |
| origin | body / attachment |
| attachment_id | |
| locator | 문단 번호, 페이지, 셀 위치 |
| quote | 원문 그대로의 짧은 구절 |

## plans — 기획
| id, type (single / bundle / trend / questions) |
| item_ids | json |
| title, angle, summary |
| payload | json (기획별 구조, prompts 참조) |
| source_ref_ids | json |

## candidates — 오늘의 후보
| id, date, rank, plan_id |
| total_score, feature_scores | json |
| slot | main / explore |
| reason | 한 줄 |
| weights_version | 계산에 쓴 가중치 버전 |

## ratings — 평가
| id, candidate_id, score (1~5), tag (adopt / hold / drop / follow), comment, rated_at |

## weight_versions — 가중치 이력
| version, weights (json), category_bias (json), reason, created_at |

## articles / article_versions
| article: id, plan_id, publication, status, current_version |
| version: article_id, version, markdown, jsonld, evidence_map (json), edited_by, created_at |

evidence_map: `[{sentence_index, source_ref_ids, status: grounded|ungrounded}]`

## cardnews
| id, article_id, ratio, slides (json, templates/cardnews.schema.json), status |

## handoffs — 연계 내보내기
| id, target (content_converter / graphic_engineer), article_id, path, created_at |

## status_log — 상태 변경 기록
| entity, entity_id, from, to, actor, at |

## job_log — 작업 기록
| job (poll / recommend / backup / ai_call), started_at, ended_at, ok, counts (json), cost_estimate, error |
