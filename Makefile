fmt:
	npm run fmt

fmt-check:
	npm run fmt:check

up:
	docker compose up

down:
	docker compose down

logs:
	docker compose logs -f